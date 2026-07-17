import { useEffect, useState } from "react";
import { API_BASE_CANDIDATE_DISPLAY_URLS, API_BASE_DISPLAY_URL, CONFIGURED_API_BASE_DISPLAY_URL, getAuditCache, getAuditUserRouteQa, getBootstrapStatus, getCandidateRadarCache, getChokepointCache, getDataCapabilityCache, getDataHealthCache, getDesktopPreflightCache, getDisciplineLoopCache, getFactorQuantCache, getHealth, getLegacyBridgeCache, getMarketContextCache, getMigrationStatus, getModelStrategyCache, getNextSessionCache, getPacket, getPackets, getPositionCache, getRecoveryCenterCache, getRiskGuardrailsCache, getSerenityCache, getStorageCatalog, getStorageCurrentResult, getStorageOverview, getTaskCatalog, getTasks, getWorkerRuntimeCache, postBootstrapLiveStartup, postCandidateRadarQuantProjection, type TaskCreationEnvelope, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import RouteCacheLoadingOverlay from "../components/RouteCacheLoadingBoundary";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const LIVE_BOOTSTRAP_SESSION_KEY = "command_center_3_live_bootstrap_session_key";
const DATA_CAPABILITY_HREF = "#dataCapability";

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

function homeRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function homeText(value: unknown, fallback = "--") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function ordinaryHomeText(value: unknown, fallback = "--") {
  return homeText(value, fallback)
    .replace(/Tushare-first/gi, "真实数据链")
    .replace(/Tushare/gi, "真实数据")
    .replace(/DeepSeek/gi, "模型解释")
    .replace(/POST task/gi, "手动后台流程")
    .replace(/task receipt/gi, "本地确认记录")
    .replace(/task id/gi, "本地任务编号")
    .replace(/task/gi, "后台流程")
    .replace(/scope hash/gi, "范围校验")
    .replace(/payload/gi, "请求摘要")
    .replace(/call_ledger/gi, "数据记录")
    .replace(/ledger/gi, "数据记录")
    .replace(/packet/gi, "结果包")
    .replace(/cache/gi, "本地缓存")
    .replace(/provider/gi, "数据源")
    .replace(/model/gi, "模型")
    .replace(/React render/gi, "页面渲染")
    .replace(/GET cache/gi, "本地缓存读取")
    .replace(/strategy action/gi, "交易策略")
    .replace(/degraded/gi, "待补")
    .replace(/pending/gi, "等待中")
    .replace(/receipt/gi, "记录")
    .replace(/legacy/gi, "旧工作台")
    .replace(/research-only/gi, "仅作研究辅助")
    .replace(/账本/g, "数据记录");
}

function ordinaryHomeMetricItems(items: MetricItem[]) {
  return items.map((item) => ({
    ...item,
    label: ordinaryHomeText(item.label),
    value: ordinaryHomeText(item.value),
    tone: undefined
  }));
}

function latestHomeTushareTaskSummary(tasks: Array<Record<string, unknown>>) {
  const safeLedger = (task: Record<string, unknown>) => homeRows(task.call_ledger);
  const isTushareLedgerRow = (row: Record<string, unknown>) => {
    const api = homeText(row.api, "").toLowerCase();
    return row.tushare_called === true ||
      ["trade_cal", "daily", "daily_basic", "moneyflow", "fund_daily", "margin_detail"].includes(api);
  };
  const task = tasks.find((item) => {
    const taskType = homeText(item.task_type, "").toLowerCase();
    return taskType.includes("tushare") || safeLedger(item).some(isTushareLedgerRow);
  });
  if (!task) {
    return {
      ready: false,
      status: "waiting_tushare_task",
      taskId: "",
      symbol: "",
      apis: "",
      dataDate: "",
      rowCount: 0,
      scopeHashShort: "",
      failureMode: "waiting_confirm_task",
      label: "等待确认后的真实数据任务"
    };
  }
  const payload = (task.payload_safe && typeof task.payload_safe === "object" ? task.payload_safe : {}) as Record<string, unknown>;
  const ledgerRows = safeLedger(task).filter(isTushareLedgerRow);
  const apis = Array.from(new Set(ledgerRows.map((row) => homeText(row.api, "")).filter(Boolean)));
  const rowCount = ledgerRows.reduce((total, row) => total + Number(row.row_count ?? 0), 0);
  const firstDataDate = ledgerRows.map((row) => homeText(row.data_date, "")).find(Boolean) ?? "";
  const firstScopeHashShort = ledgerRows.map((row) => homeText(row.scope_hash_short ?? row.scope_hash, "")).find(Boolean) ?? "";
  const failureModes = Array.from(new Set(ledgerRows
    .map((row) => homeText(row.failure_mode, ""))
    .filter((value) => value && value !== "none")));
  const symbol = homeText(payload.symbol ?? payload.ts_code ?? ledgerRows[0]?.symbol ?? ledgerRows[0]?.ts_code, "");
  const status = homeText(task.status, "unknown");
  const ready = status === "success" && rowCount > 0 && failureModes.length === 0;
  return {
    ready,
    status,
    taskId: homeText(task.task_id, ""),
    symbol,
    apis: apis.join(" / "),
    dataDate: firstDataDate,
    rowCount,
    scopeHashShort: firstScopeHashShort.slice(0, 16),
    failureMode: failureModes.join(" / ") || (rowCount > 0 ? "none" : "empty_or_missing_rows"),
    label: `${symbol || "当前标的"} · ${apis.join(" / ") || "Tushare"} · ${firstDataDate || "等待日期"} · ${rowCount} 行`
  };
}

export default function CommandCenterHome() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [audit, setAudit] = useState<Record<string, unknown>>({});
  const [auditUserRouteQa, setAuditUserRouteQa] = useState<Record<string, unknown>>({});
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
  const [homeQuantReadbackRefreshing, setHomeQuantReadbackRefreshing] = useState(false);
  const [homeQuantReadbackLastRefresh, setHomeQuantReadbackLastRefresh] = useState("");
  const [packets, setPackets] = useState<Record<string, unknown>>({});
  const [homeEtfPacket, setHomeEtfPacket] = useState<Record<string, unknown>>({});
  const [homeMarginPacket, setHomeMarginPacket] = useState<Record<string, unknown>>({});
  const [homeMarginEtfReceipt, setHomeMarginEtfReceipt] = useState<Record<string, unknown>>({});
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
  const [dataCapabilityCache, setDataCapabilityCache] = useState<Record<string, unknown>>({});
  const [dataCapabilityEnvelopeLedger, setDataCapabilityEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
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
  const [storageCurrentResult, setStorageCurrentResult] = useState<Record<string, unknown>>({});
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
  const [auditReadbackRequested, setAuditReadbackRequested] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const initialLayoutReady = !loading;

  useEffect(() => {
    let cancelled = false;
    let secondaryPending = 0;
    let secondaryStarted = false;
    let gateTimer: number | undefined;
    let secondaryTimer: number | undefined;
    const recordRequestFailure = (label: string, err: unknown) => {
      if (cancelled) return;
      setError((current) => current || `${label}: ${err instanceof Error ? err.message : String(err)}`);
    };
    const track = <T extends { ok?: boolean; error?: string | null }>(
      label: string,
      promise: Promise<T>,
      onReady: (res: T) => void,
      options: { allowCacheMissing?: boolean } = {}
    ) => {
      secondaryPending += 1;
      void promise.then((res) => {
        if (cancelled) return;
        onReady(res);
        const allowedOptionalCacheMiss = label === "home_margin_etf_receipt"
          && options.allowCacheMissing === true
          && res.error?.startsWith("cache_missing:") === true;
        if (res.ok === false && !allowedOptionalCacheMiss) {
          setError((current) => current || `${label}: ${res.error ?? "request_not_ok"}`);
        }
      }).catch((err) => recordRequestFailure(label, err)).finally(() => {
        secondaryPending -= 1;
      });
    };
    const trackP0 = <T extends { ok?: boolean; error?: string | null }>(
      label: string,
      promise: Promise<T>,
      onReady: (res: T) => void
    ) => {
      return promise.then((res) => {
        if (cancelled) return;
        onReady(res);
        if (res.ok === false) setError((current) => current || `${label}: ${res.error ?? "request_not_ok"}`);
      }).catch((err) => recordRequestFailure(label, err));
    };
    const startOrdinaryReadback = () => {
      if (cancelled || secondaryStarted) return;
      secondaryStarted = true;
      track("home_etf_packet", getPacket("command_center_etf_packet"), (res) => setHomeEtfPacket(res.data));
      track("home_margin_packet", getPacket("command_center_margin_packet"), (res) => setHomeMarginPacket(res.data));
      track(
        "home_margin_etf_receipt",
        getPacket("command_center_margin_etf_refresh_receipt"),
        (res) => setHomeMarginEtfReceipt(res.data),
        { allowCacheMissing: true }
      );
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
      track("position", getPositionCache(), (res) => setPosition(res.data));
      track("candidates", getCandidateRadarCache(), (res) => setCandidates(res.data));
      track("storage_current_result", getStorageCurrentResult(), (res) => setStorageCurrentResult(res.data));
      track("data_health", getDataHealthCache(), (res) => setDataHealth(res.data));
    };

    const startNonBlockingGateReadback = () => {
      track("bootstrap", getBootstrapStatus(), (res) => {
        setBootstrapStatus(res.data);
        setBootstrapEnvelopeLedger(res.call_ledger ?? []);
        setBootstrapEnvelopeWarnings(res.warnings ?? []);
      });
      track("desktop_preflight", getDesktopPreflightCache(), (res) => setDesktopPreflight(res.data));
      track("tasks", getTasks(), (res) => {
        setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
        setTaskIndex(res.data);
        setTasks(res.data.tasks ?? []);
      });
    };

    setLoading(true);
    setError("");
    const p0Jobs = [
      trackP0("health", getHealth(), (res) => {
        setHealth(res.data);
        setHealthEnvelopeLedger(res.call_ledger ?? []);
        setHealthEnvelopeWarnings(res.warnings ?? []);
      }),
    ];
    void Promise.allSettled(p0Jobs).then(() => {
      if (cancelled) return;
      setLoading(false);
      gateTimer = window.setTimeout(startNonBlockingGateReadback, 520);
      secondaryTimer = window.setTimeout(startOrdinaryReadback, 650);
    });

    return () => {
      cancelled = true;
      if (gateTimer !== undefined) window.clearTimeout(gateTimer);
      if (secondaryTimer !== undefined) window.clearTimeout(secondaryTimer);
    };
  }, []);

  useEffect(() => {
    if (!auditReadbackRequested) return;
    let cancelled = false;
    const trackAudit = <T extends { ok?: boolean; error?: string | null }>(
      label: string,
      promise: Promise<T>,
      onReady: (res: T) => void
    ) => {
      void promise.then((res) => {
        if (cancelled) return;
        onReady(res);
        if (res.ok === false) setError((current) => current || `${label}: ${res.error ?? "request_not_ok"}`);
      }).catch((err) => {
        if (!cancelled) setError((current) => current || `${label}: ${err instanceof Error ? err.message : String(err)}`);
      });
    };

    trackAudit("audit", getAuditCache(), (res) => setAudit(res.data));
    trackAudit("audit_user_route_qa", getAuditUserRouteQa(), (res) => setAuditUserRouteQa(res.data));
    trackAudit("packets", getPackets(), (res) => {
      setPacketEnvelopeLedger(res.call_ledger ?? []);
      setPackets(res.data);
    });
    trackAudit("market", getMarketContextCache(), (res) => {
      setMarketEnvelopeLedger(res.call_ledger ?? []);
      setMarketEnvelopeWarnings(res.warnings ?? []);
      setMarket(res.data);
    });
    trackAudit("discipline", getDisciplineLoopCache(), (res) => {
      setDisciplineEnvelopeLedger(res.call_ledger ?? []);
      setDisciplineEnvelopeWarnings(res.warnings ?? []);
      setDiscipline(res.data);
    });
    trackAudit("data_capability", getDataCapabilityCache(), (res) => {
      setDataCapabilityEnvelopeLedger(res.call_ledger ?? []);
      setDataCapabilityCache(res.data);
    });
    trackAudit("recovery", getRecoveryCenterCache(), (res) => setRecovery(res.data));
    trackAudit("risk", getRiskGuardrailsCache(), (res) => setRisk(res.data));
    trackAudit("serenity", getSerenityCache(), (res) => {
      setSerenityEnvelopeLedger(res.call_ledger ?? []);
      setSerenityEnvelopeWarnings(res.warnings ?? []);
      setSerenity(res.data);
    });
    trackAudit("chokepoint", getChokepointCache(), (res) => {
      setChokepointEnvelopeLedger(res.call_ledger ?? []);
      setChokepointEnvelopeWarnings(res.warnings ?? []);
      setChokepoint(res.data);
    });
    trackAudit("storage", getStorageOverview(), (res) => setStorageOverview(res.data));
    trackAudit("storage_catalog", getStorageCatalog(), (res) => {
      setStorageCatalogEnvelopeLedger(res.call_ledger ?? []);
      setStorageCatalogEnvelopeWarnings(res.warnings ?? []);
      setStorageCatalog(res.data);
    });
    trackAudit("migration", getMigrationStatus(), (res) => setMigration(res.data));
    trackAudit("model_strategy", getModelStrategyCache(), (res) => setModelStrategy(res.data));
    trackAudit("legacy", getLegacyBridgeCache(), (res) => setLegacyBridge(res.data));
    trackAudit("task_catalog", getTaskCatalog(), (res) => {
      setTaskCatalogEnvelopeLedger(res.call_ledger ?? []);
      setTaskCatalog(res.data);
    });
    trackAudit("worker", getWorkerRuntimeCache(), (res) => setWorkerRuntime(res.data));

    return () => {
      cancelled = true;
    };
  }, [auditReadbackRequested]);

  const packetKeys = packets.available_cache_keys as unknown[] | undefined;
  const auditCounts = audit.counts as Record<string, unknown> | undefined;
  const userRouteQaEvidenceSource = Object.keys(auditUserRouteQa).length ? auditUserRouteQa : audit;
  const userRouteQaEvidence = (userRouteQaEvidenceSource.user_route_qa_evidence_contract as Record<string, unknown> | undefined) ?? {};
  const userRouteQaCoveredRoutes = Array.isArray(userRouteQaEvidence.covered_routes)
    ? (userRouteQaEvidence.covered_routes as unknown[]).map((route) => String(route))
    : [];
  const userRouteQaCoveredViewports = Array.isArray(userRouteQaEvidence.covered_viewports)
    ? (userRouteQaEvidence.covered_viewports as unknown[]).map((viewport) => String(viewport))
    : [];
  const userRouteQaRequiredRoutes = ["#home", "#candidates", "#marginEtf", "#factor", "#next"];
  const userRouteQaMissingRoutes = userRouteQaRequiredRoutes.filter((route) => !userRouteQaCoveredRoutes.includes(route));
  const userRouteQaLatestMatrixCount = Number(userRouteQaEvidence.latest_report_qa_matrix_count ?? 0);
  const userRouteQaLatestReviewRequiredCount = Number(userRouteQaEvidence.latest_report_review_required_count ?? 0);
  const userRouteQaLatestConsoleErrorCount = Number(userRouteQaEvidence.latest_report_console_error_count ?? 0);
  const userRouteQaTaskSilenceFailedCount = Number(userRouteQaEvidence.task_silence_failed_count ?? 0);
  const userRouteQaVisualComplete = userRouteQaEvidence.ordinary_route_visual_qa_complete === true;
  const userRouteQaTypingSilenceVerified = userRouteQaEvidence.typing_silence_verified === true;
  const userRouteQaLatestPassed = userRouteQaEvidence.latest_report_passed === true;
  const userRouteQaLatestScenario = homeText(userRouteQaEvidence.latest_report_candidate_result_scenario, "live");
  const userRouteQaDegradedLastGoodPassed = userRouteQaEvidence.latest_report_degraded_last_good_replay_passed === true;
  const userRouteQaScenarioWritesCache = userRouteQaEvidence.latest_report_candidate_result_scenario_writes_cache === true;
  const userRouteQaCandidatePassed = userRouteQaEvidence.candidate_route_visual_qa_passed === true ||
    userRouteQaEvidence.latest_report_candidate_route_passed === true;
  const ordinaryHomeUserRouteQaSummary = userRouteQaLatestPassed
    ? `最新普通路线 QA 已通过：${userRouteQaCoveredRoutes.join(" / ") || "等待路线列表"}；${userRouteQaCoveredViewports.join(" / ") || "等待视口"}；${userRouteQaDegradedLastGoodPassed ? "降级 last-good 回放也通过" : `场景 ${userRouteQaLatestScenario}`}。`
    : userRouteQaEvidence.latest_report_is_current_evidence === true
      ? `已有本地普通路线 QA 报告，但仍需复核：${homeText(userRouteQaEvidence.latest_report_status, "pending")}。`
      : "等待显式本地普通路线 QA；不影响当前首页使用。";
  const ordinaryHomeUserRouteQaItems: MetricItem[] = [
    {
      label: "路线覆盖",
      value: userRouteQaMissingRoutes.length
        ? `待补 ${userRouteQaMissingRoutes.join(" / ")}`
        : `已覆盖 ${userRouteQaCoveredRoutes.join(" / ")}`,
      tone: userRouteQaVisualComplete ? "good" : "warn"
    },
    {
      label: "视口覆盖",
      value: userRouteQaCoveredViewports.length ? userRouteQaCoveredViewports.join(" / ") : "等待 desktop/mobile",
      tone: userRouteQaCoveredViewports.length >= 2 ? "good" : "warn"
    },
    {
      label: "输入静默",
      value: userRouteQaTypingSilenceVerified ? "已验证：可见输入不会创建任务" : "等待显式 runner 验证",
      tone: userRouteQaTypingSilenceVerified ? "good" : "warn"
    },
    {
      label: "任务静默",
      value: userRouteQaTaskSilenceFailedCount ? `${userRouteQaTaskSilenceFailedCount} 条路线需复核` : "渲染/输入未创建任务",
      tone: userRouteQaTaskSilenceFailedCount ? "warn" : "good"
    },
    {
      label: "候选页",
      value: userRouteQaCandidatePassed ? "下一票雷达 desktop/mobile 已在本地 QA 覆盖" : "等待下一票雷达路线 QA",
      tone: userRouteQaCandidatePassed ? "good" : "warn"
    },
    {
      label: "降级回放",
      value: userRouteQaDegradedLastGoodPassed
        ? "last-good 保留；旧任务不能覆盖 current"
        : `场景 ${userRouteQaLatestScenario}`,
      tone: userRouteQaDegradedLastGoodPassed || userRouteQaLatestScenario === "live" ? "good" : "warn"
    },
    {
      label: "最新报告",
      value: `${homeText(userRouteQaEvidence.latest_report_status, "missing")} / matrix ${userRouteQaLatestMatrixCount} / review ${userRouteQaLatestReviewRequiredCount} / console ${userRouteQaLatestConsoleErrorCount}`,
      tone: userRouteQaLatestPassed ? "good" : "warn"
    },
    {
      label: "边界",
      value: "首页只读 ignored 本地 QA 摘要；不打开浏览器、不提交截图、不调用外部服务",
      tone: "good"
    }
  ];
  const ordinaryHomeUserRouteQaRows = userRouteQaRequiredRoutes.map((route) => ({
    路线: route,
    当前状态: userRouteQaCoveredRoutes.includes(route) ? "latest passing report covered" : "waiting explicit local QA",
    用户看法: route === "#home"
      ? "首页首屏是否清楚、确认输入是否静默"
      : route === "#candidates"
        ? "下一票雷达候选池、确认按钮和非买入边界是否清楚"
        : route === "#marginEtf"
          ? "ETF/融资风险预算、逐行读法和非加融资边界是否清楚"
          : route === "#factor"
            ? "股票量化推演、Factor 支持/压制和 provider 缺口是否清楚"
            : "次日图谱、操作区条件和非交易边界是否清楚",
    视口: userRouteQaCoveredViewports.length ? userRouteQaCoveredViewports.join(" / ") : "waiting desktop/mobile",
    边界: "只读本地 QA 摘要；不创建任务、不调用外部数据或模型、不交易"
  }));
  ordinaryHomeUserRouteQaRows.push({
    路线: "degraded-last-good",
    当前状态: userRouteQaDegradedLastGoodPassed
      ? "latest QA replay retained last-good and blocked stale overwrite"
      : `latest scenario ${userRouteQaLatestScenario}`,
    用户看法: "失败/缺事实场景下旧 current 结果是否继续可读，旧任务是否不会覆盖新标的",
    视口: userRouteQaCoveredViewports.length ? userRouteQaCoveredViewports.join(" / ") : "waiting desktop/mobile",
    边界: userRouteQaScenarioWritesCache
      ? "需要复核：QA replay 不应写 cache"
      : "只读本地 QA replay；不写 cache、不创建任务、不调用外部数据或模型、不交易"
  });
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
  const ordinaryHomeDataFreshness = (dataHealth.data_freshness as Record<string, unknown> | undefined) ?? {};
  const ordinaryHomeDataDate = homeText(
    ordinaryHomeDataFreshness.data_date ?? dataHealth.data_date,
    ""
  );
  const ordinaryHomeAsOfDate = homeText(
    ordinaryHomeDataFreshness.as_of_date ?? dataHealth.as_of_date,
    ""
  );
  const ordinaryHomeExpectedTradeDate = homeText(
    ordinaryHomeDataFreshness.expected_trade_date ?? dataHealth.expected_trade_date,
    ""
  );
  const ordinaryHomeCalendarValidated =
    ordinaryHomeDataFreshness.expected_trade_date_calendar_validated === true ||
    dataHealth.expected_trade_date_calendar_validated === true;
  const ordinaryHomeFreshnessSourceLabel = homeText(
    ordinaryHomeDataFreshness.label ?? dataHealth.label,
    ""
  ).toLowerCase();
  const ordinaryHomeFreshnessState = homeText(
    ordinaryHomeDataFreshness.freshness_state ??
      ordinaryHomeDataFreshness.state ??
      ordinaryHomeDataFreshness.status ??
      dataHealth.freshness_state ??
      dataHealth.state,
    ""
  ).toLowerCase() || ordinaryHomeFreshnessSourceLabel;
  const ordinaryHomeFreshnessAgeDays = homeText(
    ordinaryHomeDataFreshness.age_calendar_days ??
      ordinaryHomeDataFreshness.age_days ??
      dataHealth.age_calendar_days ??
      dataHealth.age_days,
    ""
  );
  const ordinaryHomeDataDateMatchesExpected = Boolean(
    ordinaryHomeDataDate &&
      ordinaryHomeExpectedTradeDate &&
      ordinaryHomeDataDate === ordinaryHomeExpectedTradeDate
  );
  const ordinaryHomeFreshnessIsFresh =
    ordinaryHomeCalendarValidated &&
    ordinaryHomeDataDateMatchesExpected &&
    ["fresh", "fresh_provider", "current", "today"].includes(ordinaryHomeFreshnessState);
  const ordinaryHomeFreshnessIsStale =
    ordinaryHomeFreshnessState.includes("stale") ||
    ordinaryHomeFreshnessState.includes("cache") ||
    ordinaryHomeFreshnessState.includes("缓存") ||
    Boolean(
      ordinaryHomeDataDate &&
        ordinaryHomeExpectedTradeDate &&
        !ordinaryHomeDataDateMatchesExpected
    );
  const ordinaryHomeFreshnessLabel = ordinaryHomeFreshnessIsFresh
    ? "fresh"
    : ordinaryHomeFreshnessIsStale
      ? "stale"
      : "unknown";
  const ordinaryHomeFreshnessExplanation = ordinaryHomeFreshnessIsFresh
    ? "交易日历已验证，数据日期与当前交易日一致。"
    : ordinaryHomeFreshnessIsStale
      ? "缓存日期未满足当前交易日；不按今日数据展示。"
      : ordinaryHomeCalendarValidated
        ? "数据日期或新鲜度状态待确认；不按今日数据展示。"
        : "交易日历尚未验证；不按今日数据展示。";
  const ordinaryHomeFreshnessNeedsAttention = !ordinaryHomeFreshnessIsFresh;
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
          用户下一步: "代码通过本地校验后点击确认按钮，才创建 Tushare-first POST task；模型解释单独补证。",
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
  const candidateCoarseFineScreening = (candidates.coarse_fine_screening_contract as Record<string, unknown> | undefined) ?? {};
  const candidateTopWatchExcludedRows = homeRows(candidates.top_watch_excluded_group_rows);
  const candidateHomeRows = homeRows(candidates.candidate_rows);
  const candidateScanExecutionSummary = (candidates.scan_execution_summary as Record<string, unknown> | undefined) ?? {};
  const candidatePolicy = (candidates.policy as Record<string, unknown> | undefined) ?? {};
  const candidateQuantReceipt = (candidates.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateQuantSmallDataWriteback = (candidates.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const candidateQuantProviderModelAcceptance = (candidates.search_quant_provider_model_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateQuantCurrentResultLineage = (candidates.search_quant_current_result_lineage as Record<string, unknown> | undefined) ?? {};
  const candidateQuantLastGoodResultLineage = (candidates.search_quant_last_good_result_lineage as Record<string, unknown> | undefined) ?? {};
  const candidateQuantDegradedResultLineage = (candidates.search_quant_degraded_result_lineage as Record<string, unknown> | undefined) ?? {};
  const candidateQuantResultLineage =
    (candidates.search_quant_canonical_result_lineage as Record<string, unknown> | undefined) ??
    (candidates.search_quant_result_lineage as Record<string, unknown> | undefined) ??
    (candidateQuantProviderModelAcceptance.result_lineage as Record<string, unknown> | undefined) ??
    {};
  const candidateQuantResultVersionSummary =
    (candidates.search_quant_result_version_summary as Record<string, unknown> | undefined) ??
    (candidateQuantProviderModelAcceptance.result_version_summary as Record<string, unknown> | undefined) ??
    {};
  const dailyCommandCurrentResultSymbol = homeText(
    candidateQuantResultVersionSummary.current_result_symbol ?? candidateQuantCurrentResultLineage.symbol,
    ""
  );
  const dailyCommandCurrentResultVersion = homeText(
    candidateQuantResultVersionSummary.current_result_version ??
      candidateQuantResultVersionSummary.canonical_result_version ??
      candidateQuantCurrentResultLineage.result_version ??
      candidateQuantResultLineage.result_version,
    ""
  );
  const dailyCommandCurrentResultLabel = dailyCommandCurrentResultVersion
    ? `${dailyCommandCurrentResultSymbol || "当前结果"} / ${dailyCommandCurrentResultVersion}`
    : "成功后才提升 current result";
  const dailyCommandLatestResultSymbol = homeText(
    candidateQuantResultVersionSummary.latest_task_symbol ??
      candidateQuantResultLineage.latest_attempt_symbol ??
      candidateQuantResultLineage.symbol ??
      candidateQuantProviderModelAcceptance.symbol,
    ""
  );
  const dailyCommandLatestResultVersion = homeText(
    candidateQuantResultVersionSummary.latest_task_result_version ??
      candidateQuantResultVersionSummary.latest_result_version ??
      candidateQuantResultLineage.latest_attempt_result_version ??
      candidateQuantResultLineage.result_version ??
      candidateQuantProviderModelAcceptance.result_version,
    ""
  );
  const dailyCommandLatestResultLabel = dailyCommandLatestResultVersion
    ? `${dailyCommandLatestResultSymbol || "最新尝试"} / ${dailyCommandLatestResultVersion}`
    : "等待确认后的结果版本";
  const dailyCommandLastGoodResultSymbol = homeText(
    candidateQuantResultVersionSummary.last_good_result_symbol ?? candidateQuantLastGoodResultLineage.symbol,
    ""
  );
  const dailyCommandLastGoodResultVersion = homeText(
    candidateQuantResultVersionSummary.last_good_result_version ?? candidateQuantLastGoodResultLineage.result_version,
    ""
  );
  const dailyCommandLastGoodResultLabel = dailyCommandLastGoodResultVersion
    ? `${dailyCommandLastGoodResultSymbol || "last-good"} / ${dailyCommandLastGoodResultVersion}`
    : "暂无 last-good";
  const dailyCommandDegradedResultVisible =
    candidateQuantResultVersionSummary.degraded_result_visible === true ||
    Boolean(candidateQuantResultVersionSummary.degraded_result_version) ||
    Boolean(candidateQuantDegradedResultLineage.result_version);
  const dailyCommandDegradedResultSymbol = homeText(
    candidateQuantResultVersionSummary.degraded_result_symbol ??
      candidateQuantDegradedResultLineage.symbol ??
      candidateQuantResultVersionSummary.latest_task_symbol,
    ""
  );
  const dailyCommandResultVersionGuardReady =
    candidateQuantResultVersionSummary.old_task_can_overwrite_current === false ||
    candidateQuantResultLineage.old_task_can_overwrite_current === false;
  const dailyCommandResultVersionGuardLabel = dailyCommandResultVersionGuardReady
    ? "旧任务不能覆盖 current；只按 symbol + result_version 提升结果"
    : "等待 symbol + result_version 覆盖保护";
  const candidateQuantSmallDataReadbackCheckpoint =
    (candidates.search_quant_projection_small_data_readback_checkpoint as Record<string, unknown> | undefined) ?? {};
  const candidateQuantP2ThreeSurfaceCheckpoint =
    (candidates.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ??
    {};
  const candidateQuantP1ShortestPathCheckpoint =
    (candidates.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ??
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
  const candidateQuantProviderApiRows =
    (candidates.ordinary_provider_api_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_provider_api_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantWritebackSurfaceRows =
    (candidates.search_quant_projection_small_data_writeback_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_writeback_surface_summary_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantConfirmChainCheckpoint = (candidates.search_quant_projection_confirm_chain_checkpoint as Record<string, unknown> | undefined) ?? {};
  const dailyCommandTushareFirstLedgerReady =
    candidates.search_quant_projection_p1_shortest_path_ready === true ||
    candidateQuantConfirmChainCheckpoint.provider_ledger_ready === true ||
    candidateQuantReceipt.p1_tushare_first_provider_ledger_ready === true ||
    candidateQuantSmallDataWriteback.source_task_tushare_provider_ledger_ready === true ||
    candidateQuantSmallDataWriteback.provider_call_ledger_replayed_from_source_task === true ||
    candidateQuantSmallDataWriteback.provider_call_ledger_written === true ||
    candidateQuantSmallDataWriteback.ledger_ready === true ||
    Number(candidateQuantSmallDataWriteback.provider_api_success_count ?? 0) > 0;
  const dailyCommandTushareFirstApiCount = Number(
    candidates.search_quant_projection_p1_provider_api_call_count ??
      candidateQuantConfirmChainCheckpoint.provider_api_call_count ??
      candidateQuantSmallDataWriteback.provider_call_ledger_api_count ??
      0
  );
  const dailyCommandTushareFirstSuccessCount = Number(
    candidates.search_quant_projection_p1_provider_api_success_count ??
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
    ? `Tushare-first 数据已回放：${dailyCommandTushareFirstSuccessCount}/${dailyCommandTushareFirstApiCount} 个接口`
    : "等待确认按钮后的 Tushare-first 数据回放";
  const dailyCommandTushareFirstDeepSeekLabel =
    candidateQuantConfirmChainCheckpoint.deepseek_called_from_confirm_chain === false ||
    candidateQuantReceipt.p1_deepseek_skipped_by_request === true
      ? "模型解释单独补证：P5 governed executor 单独补"
      : "DeepSeek 等 governed executor；不阻塞 P1/P2/P3";
  const dailyCommandTushareFirstBoundary =
    "P1 只允许首页或下一票雷达确认按钮创建 Tushare-first 后台确认；首页回放卡只读本地结果，不重复启动确认链。";
  const dailyCommandP1ShortestPathReady =
    candidates.search_quant_projection_p1_shortest_path_ready === true ||
    candidateQuantP1ShortestPathCheckpoint.tushare_first_ledger_ready === true ||
    dailyCommandTushareFirstLedgerReady;
  const dailyCommandP1ShortestPathStatus = String(
    candidates.search_quant_projection_p1_shortest_path_status ??
      candidateQuantP1ShortestPathCheckpoint.status ??
      (dailyCommandP1ShortestPathReady ? "tushare_first_ledger_replayed" : "waiting_symbol_confirm")
  );
  const dailyCommandP1ShortestPathLabel = String(
    candidates.search_quant_projection_p1_shortest_path_summary ??
      candidateQuantP1ShortestPathCheckpoint.ordinary_label ??
      (dailyCommandP1ShortestPathReady ? dailyCommandTushareFirstLedgerLabel : "P1 等待输入股票代码并点击确认。")
  );
  const dailyCommandP1ShortestPathNext = String(
    candidates.search_quant_projection_p1_shortest_path_next_step ??
      candidateQuantP1ShortestPathCheckpoint.next_action ??
      (dailyCommandP1ShortestPathReady
        ? "直接回放股票量化推演和次日图谱；DeepSeek 仍等 P5 governed executor。"
        : "先输入股票代码并点击确认按钮；输入本身保持静默。")
  );
  const dailyCommandP1ShortestPathBoundary = String(
    candidates.search_quant_projection_p1_shortest_path_boundary ??
      "P1 最短路径 checkpoint 只读 CandidateRadar cache；不创建第二个 task、不补调 Tushare/DeepSeek、不展示敏感凭据、不交易。"
  );
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
          链路段: "3. Tushare 数据",
          当前状态: dailyCommandTushareFirstLedgerLabel,
          用户下一步: "数据可回放后继续看 P2 三面和 P3 结论",
          证据: "确认任务回放",
          边界: "Tushare 只允许按钮门控后台确认调用；GET cache 只读回放。"
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
      "等待确认按钮后的本地三面回放"
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
    candidates.search_quant_projection_p2_three_surface_summary ??
      candidateQuantP2ThreeSurfaceCheckpoint.ordinary_label ??
      candidateQuantSmallDataReadbackCheckpoint.ordinary_readback_summary ??
      dailyCommandSmallDataWritebackState
  );
  const dailyCommandP2CheckpointStatus = String(
    candidates.search_quant_projection_p2_three_surface_status ??
      candidateQuantP2ThreeSurfaceCheckpoint.status ??
      candidateQuantSmallDataReadbackCheckpoint.status ??
      "p2_three_surface_waiting_symbol_confirm"
  );
  const dailyCommandP2CheckpointNextAction = String(
    candidates.search_quant_projection_p2_three_surface_next_step ??
      candidateQuantP2ThreeSurfaceCheckpoint.ordinary_next_action ??
      candidateQuantSmallDataReadbackCheckpoint.next_action ??
      (dailyCommandP2CheckpointStatus === "p2_three_surface_ready"
        ? "继续查看量化推演和次日图谱只读结果；DeepSeek 留到 P5 governed executor。"
        : "确认任务完成后刷新本地三面回放。")
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
    candidates.search_quant_projection_p2_three_surface_ready === true ||
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
  const dailyCommandP2MissingSurfaces = [
    dailyCommandP2CacheReady ? "" : "缓存",
    dailyCommandP2LedgerReady ? "" : "数据凭证",
    dailyCommandP2PacketReady ? "" : "结果包"
  ].filter(Boolean);
  const dailyCommandP2MissingSurfaceLabel = dailyCommandP2MissingSurfaces.length
    ? dailyCommandP2MissingSurfaces.join(" / ")
    : "无缺口";
  const dailyCommandP2SymbolLabel = String(
    candidateQuantP2ThreeSurfaceCheckpoint.symbol ??
      candidateQuantSmallDataReadbackCheckpoint.symbol ??
      candidateQuantSmallDataWriteback.symbol ??
      "等待当前标的"
  );
  const dailyCommandP2OrdinaryOneLine = dailyCommandP2ThreeSurfaceReady
    ? `${dailyCommandP2SymbolLabel} P2 三面齐备：缓存、数据凭证、结果包都可回放；下一步看股票量化推演和次日图谱。`
    : `${dailyCommandP2SymbolLabel} P2 还缺 ${dailyCommandP2MissingSurfaceLabel}；先看确认进度，完成后刷新本地三面。`;
  const dailyCommandP2VisibleWritebackSentence = dailyCommandP2ThreeSurfaceReady
    ? `${dailyCommandP2SymbolLabel} P2 写入已可见：本地缓存可刷新回放，来源记录来自确认任务，结果链已落到本地；只读回放，不等于生产验收完成。`
    : `${dailyCommandP2SymbolLabel} P2 写入待齐：还缺 ${dailyCommandP2MissingSurfaceLabel}；不要从回放卡重复创建任务，等确认任务完成后刷新本地三面。`;
  const dailyCommandP2OrdinaryNextAction = dailyCommandP2ThreeSurfaceReady
    ? "直接打开股票量化推演和次日图谱"
    : dailyCommandP2LedgerReady || dailyCommandP2CacheReady || dailyCommandP2PacketReady
      ? "按缺口补齐本地三面；不要从回放卡重复创建任务"
      : "先点击确认按钮并等待本地回放";
  const dailyCommandSmallDataWritebackBoundary =
    "P2 小数据只从 CandidateRadar 本地三面结果回放；首页 GET cache 不创建 task、不补调 Tushare/DeepSeek、不展示敏感凭据或原始日志。";
  const dailyCommandP2CheckpointBoundary = String(
    candidates.search_quant_projection_p2_three_surface_boundary ??
      "P2 三面 checkpoint 只读 CandidateRadar 本地三面结果；不重复启动确认链、不补调数据源或模型、不生成交易动作。"
  );
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
      value: "只读三面证明；不创建 task、不补调 provider/model、不展示敏感凭据或 raw log；不展示 token/key/raw log",
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
    (candidates.search_quant_projection_p3_result_rows as Array<Record<string, unknown>> | undefined) ??
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
    candidates.search_quant_projection_p3_readable_result_summary ??
      candidates.ordinary_result_summary ??
      candidateQuantInterpretation.ordinary_result_summary ??
      "等待搜票确认后的可解释结果"
  );
  const ordinaryHomeExplainableResultLabel = dailyCommandExplainableResultLabel
    .replace(/Tushare-first 账本/gi, "真实数据记录")
    .replace(/Tushare-first/gi, "真实数据")
    .replace(/DeepSeek/gi, "模型解释")
    .replace(/call_ledger/gi, "本地调用记录")
    .replace(/packet/gi, "结果包")
    .replace(/provider/gi, "外部数据")
    .replace(/ledger/gi, "数据记录");
  const dailyCommandExplainableResultNext = String(
    candidates.search_quant_projection_p3_readable_result_next_step ??
      candidates.ordinary_result_next_step ??
      candidateQuantInterpretation.ordinary_result_next_step ??
      "先进入下一票雷达输入代码并点击确认"
  );
  const dailyCommandExplainableResultBoundary = String(
    candidates.search_quant_projection_p3_readable_result_boundary ??
      candidates.ordinary_result_boundary ??
      candidateQuantInterpretation.ordinary_result_boundary ??
      "可解释结果只从本地 cache / ledger / packet 回放；不会从结果回放卡创建 task、调用模型或生成交易动作。"
  );
  const taskIndexLatestConfirmedSymbol =
    taskIndex?.latest_confirmed_symbol_readback_external_calls_triggered === true ||
    taskIndex?.latest_confirmed_symbol_creates_task_from_readback === true
      ? ""
      : homeText(taskIndex?.latest_confirmed_symbol, "");
  const dailyCommandConfirmedSymbol =
    [
      candidates.search_quant_projection_latest_confirmed_symbol,
      candidateQuantReceipt.symbol,
      candidateQuantSmallDataWriteback.symbol,
      candidateQuantInterpretation.symbol,
      taskIndexLatestConfirmedSymbol
    ]
      .map((value) => homeText(value, ""))
      .find(Boolean) ?? "";
  useEffect(() => {
    if (homeQuantSymbolTouched) return;
    if (homeQuantSymbol.trim()) return;
    if (!dailyCommandConfirmedSymbol) return;
    setHomeQuantSymbol(dailyCommandConfirmedSymbol);
  }, [dailyCommandConfirmedSymbol, homeQuantSymbol, homeQuantSymbolTouched]);
  const dailyCommandConfirmedSymbolLabel = dailyCommandConfirmedSymbol
    ? `当前确认标的：${dailyCommandConfirmedSymbol}`
    : "等待下一票雷达确认标的";
  const dataCapabilityProviderCards = homeRows(dataCapabilityCache.provider_cards);
  const dataCapabilityTushareCard = dataCapabilityProviderCards.find(
    (card) => homeText(card.provider, "").toLowerCase() === "tushare"
  ) ?? {};
  const dataCapabilityTushareAvailableCount = Number(dataCapabilityTushareCard.available_count ?? 0);
  const dataCapabilityTushareRestrictedCount = Number(dataCapabilityTushareCard.restricted_count ?? 0);
  const dataCapabilityTusharePendingCount = Number(dataCapabilityTushareCard.pending_count ?? 0);
  const dataCapabilityPayloadLedger = homeRows(dataCapabilityCache.call_ledger);
  const dataCapabilityEvidenceLedgerCount = dataCapabilityPayloadLedger.length + dataCapabilityEnvelopeLedger.length;
  const dataCapabilityMode = homeText(dataCapabilityCache.mode ?? "cache_only");
  const dataCapabilityModeLabel = dataCapabilityMode === "cache_only"
    ? "cache_only（只读缓存，不外联）"
    : `${dataCapabilityMode}（按页面边界复核）`;
  const dataCapabilityDegradedState = dataCapabilityTushareRestrictedCount
    ? "degraded：存在权限/配置受限，不能当作无数据"
    : dataCapabilityTusharePendingCount
      ? "degraded：存在空窗口、缓存或待补接口，先按保守处理"
      : dataCapabilityTushareAvailableCount
        ? "可读：已有本地数据记录可回放"
        : "等待：暂无本地数据健康记录";
  const dataCapabilityEvidenceLedgerLabel = dataCapabilityEvidenceLedgerCount
    ? `已有 ${String(dataCapabilityEvidenceLedgerCount)} 条本地数据记录可查`
    : "等待本地数据记录回读";
  const latestTushareTaskSummary = latestHomeTushareTaskSummary(tasks);
  const dailyCommandTushareLatestTaskLabel = latestTushareTaskSummary.ready
    ? `最新真实数据任务 ${latestTushareTaskSummary.taskId} 已完成：${latestTushareTaskSummary.label}`
    : latestTushareTaskSummary.taskId
      ? `最新真实数据任务 ${latestTushareTaskSummary.taskId} 状态 ${latestTushareTaskSummary.status}：${latestTushareTaskSummary.failureMode}`
      : latestTushareTaskSummary.label;
  const dailyCommandTushareLatestScopeLabel = latestTushareTaskSummary.scopeHashShort
    ? `scope ${latestTushareTaskSummary.scopeHashShort}；failure=${latestTushareTaskSummary.failureMode}`
    : `scope 等待；failure=${latestTushareTaskSummary.failureMode}`;
  const dailyCommandTushareDataCardSummary =
    dailyCommandDegradedResultVisible &&
    dailyCommandCurrentResultSymbol &&
    dailyCommandDegradedResultSymbol &&
    dailyCommandCurrentResultSymbol !== dailyCommandDegradedResultSymbol
      ? `最近尝试 ${dailyCommandDegradedResultSymbol} 已降级；首页 current 仍保留 ${dailyCommandCurrentResultSymbol}，旧任务不会覆盖 current。`
      : dailyCommandTushareFirstLedgerReady
        ? `${dailyCommandConfirmedSymbol || "当前标的"} 确认后数据链状态可读：${dailyCommandTushareFirstSuccessCount}/${dailyCommandTushareFirstApiCount} 个数据面已进入本地回放。`
        : "确认后数据链状态等待写入：先在首页或下一票雷达输入股票代码并点击确认。";
  const dailyCommandTushareDataCardNext = dailyCommandTushareFirstLedgerReady
    ? "继续看股票量化推演、P2 三面和次日图谱。"
    : "先确认股票；确认前输入保持静默，不启动确认流程。";
  const dailyCommandDataCapabilityReviewLabel = dailyCommandTushareFirstLedgerReady
    ? `真实数据凭证已有本地回放；${dataCapabilityDegradedState}。`
    : `${dataCapabilityDegradedState}；首页不探测接口。`;
  const dailyCommandTushareDataCardReviewSentence = dailyCommandTushareFirstLedgerReady
    ? "数据能力页可复核接口凭证、权限、空窗口和降级说明；首页只展示确认后的本地回放。"
    : "如果这里显示等待或 degraded，去数据能力页看权限、空窗口和本地回放缺口；首页不会补调接口。";
  const dailyCommandTushareDataCardReplayLabel = dailyCommandTushareFirstLedgerReady
    ? `${dailyCommandTushareFirstSuccessCount}/${dailyCommandTushareFirstApiCount} 个接口已有本地数据记录`
    : "等待确认后的本地数据记录";
  const dailyCommandTushareDataCardApiDetailLabel = candidateQuantProviderApiRows.length
    ? `${candidateQuantProviderApiRows.length} 行接口明细可在下一票雷达 / 量化页回放`
    : "等待接口明细回放";
  const dailyCommandTushareDataCardBoundary =
    "首页数据卡只读本地确认记录、数据调用记录和结果摘要；不创建第二次确认、不补调外部数据或模型、不交易";
  const dailyCommandTushareDataCardItems: MetricItem[] = [
    {
      label: "确认后数据链",
      value: dailyCommandTushareDataCardSummary,
      tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn"
    },
    {
      label: "接口回放",
      value: dailyCommandTushareDataCardReplayLabel,
      tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn"
    },
    {
      label: "接口明细",
      value: dailyCommandTushareDataCardApiDetailLabel,
      tone: candidateQuantProviderApiRows.length ? "good" : "warn"
    },
    {
      label: "最近真实任务",
      value: dailyCommandTushareLatestTaskLabel,
      tone: latestTushareTaskSummary.ready ? "good" : "warn"
    },
    {
      label: "数据日期 / scope",
      value: dailyCommandTushareLatestScopeLabel,
      tone: latestTushareTaskSummary.scopeHashShort ? "good" : "warn"
    },
    {
      label: "当前可用结果",
      value: dailyCommandCurrentResultLabel,
      tone: dailyCommandCurrentResultVersion ? "good" : "warn"
    },
    {
      label: "最新尝试",
      value: dailyCommandLatestResultLabel,
      tone: dailyCommandLatestResultVersion ? (dailyCommandDegradedResultVisible ? "warn" : "good") : "warn"
    },
    {
      label: "last-good",
      value: dailyCommandLastGoodResultLabel,
      tone: dailyCommandLastGoodResultVersion ? "good" : "warn"
    },
    {
      label: "覆盖保护",
      value: dailyCommandResultVersionGuardLabel,
      tone: dailyCommandResultVersionGuardReady ? "good" : "warn"
    },
    {
      label: "下一步",
      value: dailyCommandTushareDataCardNext,
      tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: dailyCommandDataCapabilityReviewLabel,
      tone: dataCapabilityTushareRestrictedCount || dataCapabilityTusharePendingCount ? "warn" : dailyCommandTushareFirstLedgerReady || dataCapabilityTushareAvailableCount ? "good" : "warn"
    },
    {
      label: "能力模式",
      value: dataCapabilityModeLabel,
      tone: dataCapabilityCache.cache_only === false ? "bad" : "good"
    },
    {
      label: "证据血缘",
      value: dataCapabilityEvidenceLedgerLabel,
      tone: dataCapabilityEvidenceLedgerCount ? "good" : "warn"
    },
    {
      label: "降级复核",
      value: dailyCommandTushareDataCardReviewSentence,
      tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: dailyCommandTushareDataCardBoundary,
      tone: "good"
    }
  ];
  const dailyCommandConfirmedSourceTaskLabel = String(
    candidateQuantResultCheckpoint.source_task_id ??
      candidateQuantInterpretation.source_task_id ??
      candidateQuantSmallDataWriteback.latest_task_id ??
      candidateQuantReceipt.latest_task_id ??
      candidateQuantReceipt.task_id ??
      "等待下一票雷达确认回执"
  );
  const dailyCommandP3OneGlanceReadable =
    candidates.search_quant_projection_p3_readable_result_ready === true ||
    candidateQuantResultCheckpoint.ordinary_result_readable === true ||
    candidateQuantInterpretation.interpretation_ready === true ||
    candidateQuantQuickRows.length > 0;
  const dailyCommandP3OneGlanceProviderVerified =
    candidateQuantResultCheckpoint.provider_data_source_verified === true ||
    candidateQuantResultCheckpoint.uses_tushare_ledger === true ||
    candidateQuantInterpretation.uses_tushare_ledger === true;
  const dailyCommandP3OneGlanceEvidence = String(
    candidateQuantInterpretation.ordinary_result_evidence ??
      `来源=${String(candidateQuantResultCheckpoint.evidence_source ?? "下一票雷达本地三面结果")}; 缺口=${String(candidateQuantResultCheckpoint.missing_evidence_count ?? 0)}`
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
        : "DeepSeek governed executor 单独补；普通结果只读本地三面结果";
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
          当前状态: "等待下一票雷达本地三面结果写入",
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
    candidates.search_quant_projection_p3_readable_result_status ??
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
      "等待确认回执"
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
    candidateQuantResultCheckpoint.evidence_source ?? "下一票雷达本地三面结果"
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
  const dailyCommandP3OrdinarySourceLine = dailyCommandP3OneGlanceProviderVerified
    ? `来源已接上：${dailyCommandP3OneGlanceSource}`
    : `来源待确认：${dailyCommandP3OneGlanceSource}`;
  const dailyCommandP3OrdinaryGapLine = dailyCommandP3ExplainableMissingEvidenceCount
    ? `仍有 ${String(dailyCommandP3ExplainableMissingEvidenceCount)} 项缺口：${dailyCommandP3OneGlanceMissingEvidence}`
    : "暂无额外缺口；仍只作为研究线索";
  const dailyCommandP3OrdinaryActionLine = dailyCommandP3OneGlanceUsesModelOutput
    ? "先回 P5 模型治理检查，再决定是否展示模型摘要"
    : dailyCommandExplainableResultNext;
  const dailyCommandP3OrdinaryOneLine = dailyCommandP3OneGlanceReadable
    ? `${dailyCommandConfirmedSymbolLabel} P3 可读：${dailyCommandExplainableResultLabel}；${dailyCommandP3OrdinarySourceLine}；${dailyCommandP3OrdinaryGapLine}；下一步：${dailyCommandP3OrdinaryActionLine}`
    : `${dailyCommandConfirmedSymbolLabel} P3 等待可读结论；先完成确认按钮和 P2 三面回放。`;
  const dailyCommandP3VisibleExplainableSentence = dailyCommandP3OneGlanceReadable
    ? `${dailyCommandConfirmedSymbolLabel} P3 结果可解释：结论=${dailyCommandExplainableResultLabel}；来源=${dailyCommandP3OrdinarySourceLine}；缺口=${dailyCommandP3OrdinaryGapLine}；下一步=${dailyCommandP3OrdinaryActionLine}；安全说明=只读本地结果链，不调用 DeepSeek、不生成买卖动作。`
    : `${dailyCommandConfirmedSymbolLabel} P3 等待可解释结果：先完成 P1 确认和 P2 三面，结果只从本地结果链回放。`;
  const dailyCommandP3ExplainableCheckpointStatus = String(
    dailyCommandP3ExplainableCheckpoint.status ??
      dailyCommandP3OneGlanceStatus
  );
  const dailyCommandP3ExplainableCheckpointLabel = String(
    dailyCommandP3ExplainableCheckpoint.ordinary_label ??
      dailyCommandExplainableResultLabel
  );
  const dailyCommandP3ExplainableCheckpointNextAction = String(
    dailyCommandP3ExplainableCheckpoint.ordinary_next_action ??
      dailyCommandExplainableResultNext
  );
  const dailyCommandP3ExplainableCheckpointBoundary = String(
    dailyCommandP3ExplainableCheckpoint.ordinary_result_boundary ??
      dailyCommandExplainableResultBoundary
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
      边界: candidatePolicy.search_quant_projection_task_readback_rows_are_cache_only === false ? "待复核，只能回雷达详情排查" : "首页只读 packet；不展示 raw log、token/key 或 provider error；敏感凭据仍下沉且不展示"
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
  const dailyCommandP5OrdinaryOneLine = dailyCommandP3OneGlanceUsesModelOutput
    ? "检测到模型输出：先回 P5 governed executor 审核；基础投研仍以 Tushare-first、小数据写入和本地图谱为准。"
    : "DeepSeek 当前不参与数据链：P1/P2/P3 已可用；模型解释等 P5 governed executor、model_ledger、sanitizer 和 output acceptance 完成后再补。";
  const dailyCommandP5VisibleGovernanceSentence = dailyCommandP3OneGlanceUsesModelOutput
    ? `${dailyCommandConfirmedSymbolLabel} P5 只露出非阻塞状态，P4/P6 下沉到摘要和审计；P5 需要先审：检测到模型输出；展示前必须回查 model_ledger、sanitizer、output acceptance 和白名单字段，不覆盖价格、因子、operation_zones 或 strategy action。`
    : `${dailyCommandConfirmedSymbolLabel} P5 只露出非阻塞状态，P4/P6 下沉到摘要和审计；P5 单独补：模型解释当前待治理/未启用，不阻塞 P1 Tushare-first、P2 写入或 P3 基础图谱；真实模型调用等 model_ledger、sanitizer、output acceptance 和白名单字段后再说。`;
  const dailyCommandP5WhyNotBlocking =
    "P5 是解释补证，不是价格、持仓、factor、operation_zones 或 strategy action 的数据源。";
  const dailyCommandP5ReleaseGate =
    "放行前必须有 model_ledger、sanitizer、output acceptance、白名单字段和失败回退。";
  const dailyCommandP5SafeOutput =
    "未来只允许 source / gap / next_step / safety_summary 安全摘要，不展示 raw prompt/output 或敏感凭据。";
  const dailyCommandP5OrdinaryRows = [
    {
      检查项: "普通状态",
      当前状态: dailyCommandP5OrdinaryOneLine,
      用户下一步: modelStrategyP5NextAllowedAction,
      边界: dailyCommandDeepSeekGovernanceBoundary
    },
    {
      检查项: "为什么不阻塞",
      当前状态: dailyCommandP5WhyNotBlocking,
      用户下一步: "继续确认按钮、Tushare-first 写入和基础图谱回放",
      边界: "DeepSeek 不作为数据源，也不生成买卖动作。"
    },
    {
      检查项: "放行条件",
      当前状态: dailyCommandP5ReleaseGate,
      用户下一步: "等 P5 governed executor 单独补齐后再看模型解释缓存",
      边界: dailyCommandP5SafeOutput
    }
  ];
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
    "只读 /api/factor-quant/cache 的 CandidateRadar handoff；不创建 task、不补调 Tushare/DeepSeek、不展示敏感凭据或 raw log。";
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
    "量化缓存降级只返回安全摘要和本地 builder 结果；首页不展开 raw failed packet、provider error、敏感凭据或 call_ledger。";
  const dailyCommandFactorCacheFallbackTokenBoundary =
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
      边界: `${dailyCommandFactorCacheFallbackBoundary} ${dailyCommandFactorCacheFallbackTokenBoundary}`
    }
  ];
  const nextPayloadLedger = (next.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const dailyCommandNextSessionReplaySummary =
    (next.ordinary_result_replay_summary as Record<string, unknown> | undefined) ?? {};
  const dailyCommandNextSessionChartReady =
    dailyCommandNextSessionReplaySummary.chart_ready_for_confirmed_symbol === true;
  const dailyCommandNextSessionConfirmedSymbol = String(
    dailyCommandNextSessionReplaySummary.confirmed_symbol ?? next.latest_confirmed_symbol ?? ""
  );
  const dailyCommandNextSessionChartSymbol = String(
    dailyCommandNextSessionReplaySummary.chart_symbol ?? ""
  );
  const dailyCommandNextSessionPreviewSource =
    next.button_gated_local_confirmed_symbol_preview === true
      ? "按钮门控本地预览，非 provider-backed"
      : "本地次日图谱缓存";
  const dailyCommandNextSessionStatusRaw = String(next.status ?? "");
  const dailyCommandNextSessionReadableStatus =
    dailyCommandNextSessionChartReady
      ? `次日图谱已绑定 ${dailyCommandNextSessionConfirmedSymbol || dailyCommandNextSessionChartSymbol || "当前标的"} 可读；${dailyCommandNextSessionPreviewSource}`
      : dailyCommandNextSessionStatusRaw === "ready"
        ? "次日图谱 cache 可读，但等待确认标的绑定回放"
      : dailyCommandNextSessionStatusRaw === "candidate_readable_result_replay_chart_pending"
        ? "P3 结果已接上，完整图谱待生成/刷新"
        : dailyCommandNextSessionStatusRaw
          ? `次日图谱状态：${dailyCommandNextSessionStatusRaw}`
          : "等待次日图谱缓存";
  const dailyCommandNextSessionTone: MetricItem["tone"] =
    dailyCommandNextSessionChartReady ||
    dailyCommandNextSessionStatusRaw === "ready" ||
    dailyCommandNextSessionStatusRaw === "candidate_readable_result_replay_chart_pending"
      ? "good"
      : "warn";
  const serenityPayloadLedger = (serenity.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const chokepointPayloadLedger = (chokepoint.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskCatalogPayloadLedger = (taskCatalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskIndexPayloadLedger = taskIndex?.call_ledger ?? [];
  const dailyCommandCandidateLatestTaskId =
    [
      candidateQuantResultVersionSummary.latest_task_id,
      candidateQuantResultLineage.task_id,
      candidateQuantProviderModelAcceptance.task_id,
      candidateQuantSmallDataWriteback.latest_task_id,
      candidateQuantReceipt.latest_task_id,
      candidateQuantReceipt.task_id,
      candidates.task_id,
      taskIndex?.latest_task_id
    ]
      .map((value) => homeText(value, ""))
      .find(Boolean) ?? "";
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
  const dailyCommandLatestTaskStepLower = dailyCommandLatestTaskStep.toLowerCase();
  const dailyCommandLatestConfirmReadableStatus = dailyCommandLatestTaskStepLower.includes("tushare_first_chain_submitted_deepseek_skipped")
    ? "Tushare-first 已回放；模型解释单独补证"
    : dailyCommandLatestTaskStepLower.includes("blocked_missing_credentials")
      ? "缺服务端 Tushare 凭据；未调用 provider"
    : dailyCommandLatestTaskStepLower.includes("blocked_p0_confirm_gate")
        ? "P0 本地联通闸门未通过；未调用 provider"
    : dailyCommandLatestTaskStepLower.includes("blocked_provider_ledger_missing")
          ? "真实数据记录未写齐；等待补齐本地记录"
          : dailyCommandLatestTaskStepLower.includes("blocked_execution_request")
            ? "执行申请未 ready；等待本地申请补齐"
            : dailyCommandLatestTaskStepLower.includes("blocked_invalid_symbol")
              ? "代码格式阻断；重新输入后再确认"
              : dailyCommandLatestTaskId
                ? `本地确认已接收：${dailyCommandLatestTaskStatus}`
                : "等待确认按钮";
  const dailyCommandLatestConfirmNextAction = dailyCommandLatestTaskStepLower.includes("tushare_first_chain_submitted_deepseek_skipped")
    ? "直接看股票量化推演和次日图谱回放"
    : dailyCommandLatestTaskStepLower.includes("blocked_missing_credentials")
      ? "配置服务端 Tushare 凭据后，再点击确认按钮"
      : dailyCommandLatestTaskStepLower.includes("blocked_p0_confirm_gate")
        ? "先让一键启动和本地 FastAPI/预检联通变绿，再重新确认"
        : dailyCommandLatestTaskStepLower.includes("blocked_provider_ledger_missing")
          ? "查看进度明细里的 call ledger；需要时重新确认补齐"
          : dailyCommandLatestTaskStepLower.includes("blocked_execution_request")
            ? "查看本地申请明细；确认 scope ready 后再补 Tushare-first"
            : dailyCommandLatestTaskStepLower.includes("blocked_invalid_symbol")
              ? "输入 6 位 A 股代码或带后缀代码，再点击确认"
              : dailyCommandLatestTaskId
                ? "继续看本地进度；成功后刷新 P1/P2/P3 回放"
                : "在首页输入股票代码，点击确认按钮";
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
    ? `已看到本地确认进度：${dailyCommandLatestTaskStatus}`
    : "暂无本地确认；先在首页确认股票代码，需要详情再进下一票雷达";
  const dailyCommandLatestTaskNext = dailyCommandLatestTaskId
    ? dailyCommandLatestTaskIsCandidate
      ? "看下方确认进度；成功后进入股票量化推演和次日图谱回放"
      : "看下方确认进度；按本地结果回放"
    : "在首页输入股票代码，点击“确认股票并启动数据链”";
  const dailyCommandFastApiProgressWatchLabel = dailyCommandConfirmedSymbol
    ? `${dailyCommandConfirmedSymbol} / ${dailyCommandLatestTaskStatus}`
    : dailyCommandLatestTaskId
      ? `${dailyCommandLatestTaskId} / ${dailyCommandLatestTaskStatus}`
      : "等待确认按钮后的进度";
  const dailyCommandFastApiProgressWatchNext = dailyCommandLatestTaskId
    ? "查看确认进度；再回股票量化推演和次日图谱"
    : "先在首页确认股票代码；输入本身保持静默";
  const dailyCommandLatestTaskRows = [
    {
      速读项: "最近确认",
      当前状态: dailyCommandLatestTaskLabel,
      用户下一步: dailyCommandLatestTaskNext,
      证据: dailyCommandLatestTaskId ? "本地确认记录" : "等待确认按钮",
      边界: "首页只读确认进度；不会创建新确认、不调用 Tushare/DeepSeek/GitHub、不执行真实交易。"
    },
    {
      速读项: "确认来源",
      当前状态: dailyCommandLatestTaskIsReplay ? "来自下一票雷达本地只读回放" : "来自本机确认记录",
      用户下一步: dailyCommandLatestTaskIsReplay ? "把它当最近确认链的进度回放，不当新的生产验收证据" : "继续看确认状态和本地结果",
      证据: dailyCommandLatestTaskIsReplay ? "下一票雷达本地回放" : "本机确认记录",
      边界: "本地回放不创建任务、不补调 provider/model；只帮助普通用户看到已有进度。"
    },
    {
      速读项: "当前进度",
      当前状态: dailyCommandLatestConfirmReadableStatus,
      用户下一步: dailyCommandLatestConfirmNextAction,
      证据: "本地进度回读",
      边界: "进度面板只轮询本地 FastAPI；不会自动重试、不会下单、不改交易策略。"
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
  const dailyCommandBootstrapChecked = Object.keys(bootstrapStatus).length > 0;
  const dailyCommandDesktopPreflightChecked = Object.keys(desktopPreflight).length > 0;
  const dailyCommandCacheWarning = dailyCommandHealthOk && error ? `本地 cache 回读提示：${error}` : "";
  const dailyCommandP0ReadbackPending =
    !error &&
    (!dailyCommandHealthChecked || !dailyCommandBootstrapChecked || !dailyCommandDesktopPreflightChecked);
  const dailyCommandStartupRecoveryGateExpression =
    "!dailyCommandHealthOk && (dailyCommandP0ReadbackPending || Boolean(error) || !dailyCommandHealthChecked)";
  const dailyCommandNeedsStartupRecovery =
    !dailyCommandHealthOk && !dailyCommandP0ReadbackPending && (Boolean(error) || dailyCommandHealthChecked);
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
    : dailyCommandP0ReadbackPending
    ? "正在回读本地 FastAPI、bootstrap 和 desktop preflight；请稍等几秒，不需要先去预检"
    : dailyCommandP0QuickAction
    ? dailyCommandP0QuickAction
    : "在首页输入代码并点击确认；需要详情再进下一票雷达";
  const dailyCommandPrimaryActionLabel = dailyCommandNeedsStartupRecovery
    ? "查看一键启动预检"
    : dailyCommandP0ReadbackPending
    ? "正在确认本地联通"
    : "首页确认股票代码";
  const dailyCommandHomeConfirmHref = "#home-p1-symbol-confirm";
  const dailyCommandCandidateConfirmHref = "#candidates/candidate-radar-search-quant-projection";
  const dailyCommandPrimaryActionHref = dailyCommandNeedsStartupRecovery
    ? "#desktop"
    : dailyCommandP0ReadbackPending
    ? "#home"
    : dailyCommandHomeConfirmHref;
  const dailyCommandPrimaryActionBoundary = dailyCommandNeedsStartupRecovery
    ? "主下一步只打开桌面壳预检，不启动服务、不创建 task、不刷新 provider/model"
    : dailyCommandP0ReadbackPending
    ? "加载态只等待本地 GET 回读；不启动服务、不创建 task、不刷新 provider/model"
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
  const dailyCommandP6StrictCloseoutTotal = Number(
    migrationLongTermSummary?.strict_closeout_total_count ?? migrationLongTermGoals?.length ?? 14
  );
  const dailyCommandP6StrictCloseoutDone = Number(
    migrationLongTermSummary?.strict_closeout_done_count ?? 0
  );
  const dailyCommandP6StrictCloseoutRemaining = Number(
    migrationLongTermSummary?.strict_closeout_remaining_count ??
      Math.max(dailyCommandP6StrictCloseoutTotal - dailyCommandP6StrictCloseoutDone, 0)
  );
  const dailyCommandP6StrictCloseoutState = String(
    migrationLongTermSummary?.strict_closeout ??
      (dailyCommandP6StrictCloseoutTotal ? `${dailyCommandP6StrictCloseoutDone}/${dailyCommandP6StrictCloseoutTotal}` : "待迁移状态页回读")
  );
  const dailyCommandP6OrdinaryOneLine =
    dailyCommandP6StrictCloseoutRemaining > 0
      ? `14 LTG strict closeout 尚余 ${String(dailyCommandP6StrictCloseoutRemaining)} 项；P6 只是回归门，不是完成声明。`
      : "14 LTG strict closeout 计数需要迁移状态页复核；首页不会把可用化 checkpoint 升级成完成声明。";
  const dailyCommandP6NextEvidence =
    "打开迁移状态页，按 LTG next acceptance action rows 逐项补证；下一步只按 current-head direct evidence、CI、浏览器、provider、worker、storage、package gate 逐项关闭。";
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
  const dailyCommandStatusLabel = dailyCommandHealthOk
    ? "只读入口可用"
    : dailyCommandP0ReadbackPending
      ? "本地状态读取中"
      : "等待只读入口";
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
    "前端 API client 只在本地 FastAPI 候选地址内自动联通；失败显示离线提示，不启动服务、不创建 task、不调用 provider/model、不读取敏感凭据";
  const dailyCommandP0LocalConnectionReceipt =
    (desktopPreflight.p0_local_connection_receipt as Record<string, unknown> | undefined) ?? {};
  const dailyCommandP0StabilityReady =
    oneClickStartupSummary.p0_stability_check_before_open === true ||
    dailyCommandP0LocalConnectionReceipt.p0_stability_check_before_open === true;
  const dailyCommandP0LocalLinkReady =
    oneClickStartupSummary.frontend_backend_connection_ready === true &&
    dailyCommandP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready";
  const dailyCommandP0ConnectionEvidenceReady = dailyCommandP0StabilityReady || dailyCommandP0LocalLinkReady;
  const dailyCommandP0RuntimePacketsReady =
    dailyCommandHealthOk &&
    bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" &&
    desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache";
  const dailyCommandP0QuickActionReady = p0CurrentNextActionRows.some(
    (row) => row.p1_entry_enabled === true || row.p0_ready_now === true
  );
  const dailyCommandP0ContractEvidenceReady =
    dailyCommandP0ConnectionEvidenceReady ||
    oneClickStartupSummary.status === "one_click_frontend_backend_ready" ||
    dailyCommandP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready" ||
    dailyCommandP0QuickActionReady;
  const dailyCommandP0LocalReadinessReady =
    dailyCommandP0RuntimePacketsReady &&
    dailyCommandP0ContractEvidenceReady;
  const dailyCommandP0LocalReadinessLabel = dailyCommandP0LocalReadinessReady
    ? `P0 ready：${dailyCommandFrontendBackendSelectedApiBase} 已联通，当前 React 页面已加载；可在首页确认股票代码`
    : dailyCommandP0ReadbackPending
    ? "P0 回读中：正在读取 health、bootstrap status 和 desktop preflight；暂不判断失败"
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
    : dailyCommandP0ReadbackPending
      ? "P0 回读中：正在确认本地 FastAPI、bootstrap 和 desktop preflight；请稍等几秒"
    : !dailyCommandP0LocalReadinessReady
      ? "P0 未 ready：先让本地 FastAPI、bootstrap、desktop preflight 和 P0 connection evidence 变绿"
      : homeQuantSymbolValidation.valid
        ? `已确认 ${homeQuantSymbolValidation.normalized}；点击确认才创建 Tushare-first POST task`
        : homeQuantSymbol.trim()
          ? `代码格式阻断：${homeQuantSymbolValidation.reason}；请输入 6 位 A 股代码或 002008.SZ`
          : "先输入股票代码；输入本身不会创建 task 或调用 Tushare/DeepSeek";
  const homeQuantSubmitActionHint = homeQuantCanSubmit
    ? `${homeQuantSymbolValidation.normalized} 可确认：点击一次会创建 Tushare-first POST task，返回 task id 后自动回读 cache / call_ledger / packet；模型解释单独补证，不交易、不改交易策略。`
    : homeQuantSubmitDisabledReason;
  const homeQuantP1ServerContractLine =
    "点击确认只创建一个本地后台任务：POST /api/candidate-radar/quant-projection -> run_candidate_radar_quant_projection；Tushare-first 开启，模型解释单独补证，成功后只读回放 cache / call_ledger / packet。";
  const homeQuantP0ConfirmGateEvidence = {
    schema_version: "candidate_radar_p0_confirm_gate.v1",
    p0_ready: dailyCommandP0LocalReadinessReady,
    fastapi_cache_get_ready: dailyCommandHealthOk,
    bootstrap_runtime_mode_ready: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet",
    desktop_preflight_ready: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache",
    p0_runtime_packets_ready: dailyCommandP0RuntimePacketsReady,
    p0_stability_check_ready: dailyCommandP0StabilityReady,
    p0_local_link_ready: dailyCommandP0LocalLinkReady,
    p0_connection_evidence_ready: dailyCommandP0ConnectionEvidenceReady,
    p0_quick_action_ready: dailyCommandP0QuickActionReady,
    p0_contract_evidence_ready: dailyCommandP0ContractEvidenceReady,
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
      ? "CandidateRadar cache / GET /api/tasks 最近确认 task"
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
  const dailyCommandP1VisibleProgressSentence = homeQuantVisibleTaskId
    ? `${dailyCommandConfirmedSymbolLabel} P1 已有本地确认链：task=${homeQuantVisibleTaskId}，${dailyCommandTushareFirstLedgerLabel}，${dailyCommandTushareFirstDeepSeekLabel}；这不是 14 LTG 完成声明。`
    : dailyCommandP0LocalReadinessReady
      ? "P1 等待手动确认：输入股票代码后点击确认按钮才创建 Tushare-first POST task，输入和页面打开保持静默。"
      : "P1 暂停：先让 P0 本地 FastAPI / React 联通变绿，再确认股票代码。";
  const homeQuantP1P2P3CheckpointItems: MetricItem[] = [
    { label: "一眼 checkpoint", value: homeQuantP1P2P3CheckpointLabel, tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
    { label: "P1 当前进度", value: dailyCommandP1VisibleProgressSentence, tone: homeQuantVisibleTaskId ? "good" : dailyCommandP0LocalReadinessReady ? "warn" : "bad" },
    { label: "P1 最短路径", value: dailyCommandP1ShortestPathLabel, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
    { label: "P1 task", value: homeQuantVisibleTaskId || "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "Tushare ledger", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
    { label: "P2 三面", value: dailyCommandP2CheckpointLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
    { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "Factor handoff", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
    { label: "链路 checkpoint", value: homeQuantP1P2P3CheckpointLabel, tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
    { label: "边界", value: "checkpoint 只合成现有 cache / ledger / packet；不创建 task、不补调 provider/model", tone: "good" }
  ];
  const dailyCommandUsableNowOneGlanceItems: MetricItem[] = [
    {
      label: "现在能不能用",
      value: dailyCommandP0LocalReadinessReady
        ? "能用：本地前后端已接上"
        : dailyCommandHealthOk
          ? "能看本地结果；确认按钮等待 P0 证据完整"
          : dailyCommandP0ReadbackPending
            ? "本页已打开；本地状态读取中"
            : "先恢复：本地联通未完整 ready",
      tone: dailyCommandP0LocalReadinessReady || dailyCommandHealthOk || dailyCommandP0ReadbackPending ? "good" : "warn"
    },
    { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
    { label: "最近任务", value: homeQuantVisibleTaskId ? `${homeQuantVisibleTaskId}（${homeQuantVisibleTaskSource}）` : "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
    {
      label: "P2/P3",
      value: dailyCommandP2ThreeSurfaceReady && dailyCommandP3OneGlanceReadable
        ? "P2 三面与 P3 结论已本地回放"
        : homeQuantP1P2P3CheckpointLabel,
      tone: dailyCommandP2ThreeSurfaceReady && dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "下一步",
      value: dailyCommandP0LocalReadinessReady
        ? dailyCommandP3OneGlanceReadable ? "看股票量化推演和次日图谱" : "在首页确认股票代码"
        : "打开一键启动预检",
      tone: dailyCommandP0LocalReadinessReady ? "good" : "warn"
    },
    { label: "边界", value: "只读已有 cache / ledger / packet；输入静默；确认按钮才创建 Tushare-first task；模型解释单独补证", tone: "good" }
  ];
  const dailyCommandCurrentResearchSnapshotItems: MetricItem[] = [
    { label: "最近标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
    { label: "P1 最短路径", value: dailyCommandP1ShortestPathLabel, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
    { label: "确认任务", value: homeQuantVisibleTaskId ? `${homeQuantVisibleTaskId} (${homeQuantVisibleTaskSource})` : "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "数据链", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
    { label: "P2 写入", value: dailyCommandP2SurfaceCompletionLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
    { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "次日图谱", value: dailyCommandNextSessionReadableStatus, tone: dailyCommandNextSessionTone },
    { label: "下一步", value: dailyCommandP3OneGlanceReadable ? "看股票量化推演和次日图谱" : "先确认股票代码，等待本地回放", tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "边界", value: "首屏快照只读已有 cache / ledger / packet；不会创建 task、不会补调 Tushare/DeepSeek；不会读取 token/key、不会交易或修改 strategy action", tone: "good" }
  ];
  const ordinaryHomeStorageCurrentResult = (storageCurrentResult.result as Record<string, unknown> | undefined) ?? {};
  const ordinaryHomeStorageCurrentStatus = String(storageCurrentResult.status ?? "");
  const ordinaryHomeStorageCurrentSymbol = String(ordinaryHomeStorageCurrentResult.symbol ?? "").trim().toUpperCase();
  const ordinaryHomeStorageCurrentVersion = String(
    storageCurrentResult.selected_version_id ??
      ordinaryHomeStorageCurrentResult.result_version ??
      ""
  ).trim();
  const ordinaryHomeStorageCurrentDataDate = String(
    storageCurrentResult.data_date ??
      ordinaryHomeStorageCurrentResult.data_date ??
      ""
  ).trim();
  const ordinaryHomeStorageCurrentFreshness = String(
    storageCurrentResult.freshness_state ??
      ordinaryHomeStorageCurrentResult.freshness_state ??
      ""
  ).trim();
  const ordinaryHomeStorageCurrentFreshnessLabel =
    `${ordinaryHomeStorageCurrentDataDate || "等待 data_date"} / ${ordinaryHomeStorageCurrentFreshness || "等待 freshness"}`;
  const ordinaryHomeCanonicalResultDataDate = homeText(
    candidateQuantResultVersionSummary.canonical_data_date ??
      candidateQuantResultVersionSummary.current_result_data_date ??
      candidateQuantResultLineage.data_date,
    ""
  );
  const ordinaryHomeCanonicalResultFreshness = homeText(
    candidateQuantResultVersionSummary.canonical_freshness_state ??
      candidateQuantResultVersionSummary.current_result_freshness_state ??
      candidateQuantResultLineage.freshness_state,
    ""
  );
  const ordinaryHomeCanonicalModelLedgerId = homeText(
    candidateQuantResultVersionSummary.canonical_model_ledger_id ??
      candidateQuantResultVersionSummary.current_result_model_ledger_id ??
      candidateQuantResultLineage.model_ledger_id,
    ""
  );
  const ordinaryHomeCanonicalResultInline =
    dailyCommandP3OneGlanceReadable && dailyCommandCurrentResultVersion
      ? `；结果版本 ${dailyCommandCurrentResultVersion} / ${ordinaryHomeCanonicalResultDataDate || "等待 data_date"} / ${ordinaryHomeCanonicalResultFreshness || "等待 freshness"}；模型解释 ${ordinaryHomeCanonicalModelLedgerId || dailyCommandP3OneGlanceModelState}`
      : "";
  const ordinaryHomeStorageCurrentReadable = Boolean(
    ordinaryHomeStorageCurrentStatus === "storage_current_result_cache_ready_current" &&
    ordinaryHomeStorageCurrentSymbol &&
    ordinaryHomeStorageCurrentVersion &&
    storageCurrentResult.duckdb_readback_verified === true &&
    storageCurrentResult.cache_get_creates_task === false &&
    storageCurrentResult.cache_get_writes_files === false &&
    storageCurrentResult.external_calls_triggered === false &&
    storageCurrentResult.tushare_called === false &&
    storageCurrentResult.deepseek_called === false &&
    storageCurrentResult.github_called === false &&
    storageCurrentResult.does_not_execute_trades === true &&
    storageCurrentResult.does_not_modify_strategy_action === true
  );
  const ordinaryHomeStorageCurrentText = ordinaryHomeStorageCurrentReadable
    ? `${ordinaryHomeStorageCurrentSymbol} 本地 current-result 可读；版本 ${ordinaryHomeStorageCurrentVersion}；日期/新鲜度 ${ordinaryHomeStorageCurrentFreshnessLabel}；DuckDB 回读已通过。`
    : "Storage current-result 仍待生成或降级回放。";
  const ordinaryHomeStorageCurrentSource = ordinaryHomeStorageCurrentReadable
    ? `Storage current-result / ${String(storageCurrentResult.source_atomic_task_id ?? "本地原子提升记录")}`
    : "等待 Storage current-result 本地回放";
  const ordinaryHomeStorageCurrentGap = ordinaryHomeStorageCurrentReadable
    ? "Storage current-result 已可读；仍不等于 LTG-05 production complete"
    : "缺 current-result 本地提升或可读 last-good";
  const ordinaryHomeStorageCurrentMatchesCanonical =
    !dailyCommandCurrentResultVersion ||
    !ordinaryHomeStorageCurrentVersion ||
    ordinaryHomeStorageCurrentVersion === dailyCommandCurrentResultVersion;
  const ordinaryHomeStorageCurrentInline = ordinaryHomeStorageCurrentReadable && ordinaryHomeStorageCurrentMatchesCanonical
    ? `；current-result ${ordinaryHomeStorageCurrentVersion} / ${ordinaryHomeStorageCurrentFreshnessLabel} / DuckDB 已回读`
    : ordinaryHomeStorageCurrentReadable && dailyCommandP3OneGlanceReadable
      ? "；Storage current-result 待同步最新 result_version，首页最近结果以 Candidate canonical 为准"
    : "";
  const ordinaryHomeReadableResultReady = dailyCommandP3OneGlanceReadable || ordinaryHomeStorageCurrentReadable;
  const dailyCommandCurrentResearchSnapshotReadableSentence = homeQuantP1P2P3CheckpointReady
    ? `${dailyCommandConfirmedSymbolLabel} 已有最近确认结果：${ordinaryHomeExplainableResultLabel}；P2 ${dailyCommandP2SurfaceCompletionLabel}；${dailyCommandNextSessionReadableStatus}；下一步看股票量化推演和次日图谱。`
    : ordinaryHomeStorageCurrentReadable
      ? `${ordinaryHomeStorageCurrentSymbol} 已有本地 current-result：${ordinaryHomeStorageCurrentVersion} / ${ordinaryHomeStorageCurrentFreshnessLabel}；下一步看股票量化推演和次日图谱。`
    : dailyCommandP0LocalReadinessReady
      ? dailyCommandConfirmedSymbol
        ? `${dailyCommandConfirmedSymbolLabel} 已有本地回放线索；${homeQuantP1P2P3CheckpointLabel}；需要更新时再手动点击确认按钮。`
        : "本地联通已 ready；先在首页输入股票代码并点击确认，输入本身保持静默。"
      : "P0 本地联通还没全部 ready；先看一键启动预检，等 FastAPI、bootstrap、desktop preflight 和 React 变绿。";
  const ordinaryHomeCurrentSymbol = homeQuantSymbolValidation.valid
    ? homeQuantSymbolValidation.normalized
    : dailyCommandConfirmedSymbol || ordinaryHomeStorageCurrentSymbol || "待输入";
  const ordinaryHomeConfirmedSymbolNormalized = (dailyCommandConfirmedSymbol || ordinaryHomeStorageCurrentSymbol).trim().toUpperCase();
  const ordinaryHomeUserEditedNewSymbol =
    homeQuantSymbolTouched &&
    homeQuantSymbolValidation.valid &&
    homeQuantSymbolValidation.normalized !== ordinaryHomeConfirmedSymbolNormalized;
  const ordinaryHomeLocalDataSourceContract = {
    schema_version: "ordinary_home_local_data_source_contract.v1",
    cache_ready: dailyCommandP2CacheReady,
    ledger_ready: dailyCommandP2LedgerReady,
    packet_ready: dailyCommandP2PacketReady,
    three_surface_ready: dailyCommandP2ThreeSurfaceReady,
    label_when_ready: "本地数据已齐",
    label_when_writing: "本地数据写入中",
    label_before_confirm: "等待确认股票",
    cache_get_external_calls: false,
    readback_creates_task: false,
    ordinary_home_renders_engineering_terms: false
  };
  const ordinaryHomeLocalData = dailyCommandP2ThreeSurfaceReady
    ? ordinaryHomeLocalDataSourceContract.label_when_ready
    : ordinaryHomeStorageCurrentReadable
      ? "本地结果已可读"
    : homeQuantVisibleTaskId
      ? dailyCommandLatestTaskIsReplay
        ? "最近确认已回放"
        : ordinaryHomeLocalDataSourceContract.label_when_writing
      : dailyCommandHealthOk
        ? ordinaryHomeLocalDataSourceContract.label_before_confirm
        : "等待连接";
  const ordinaryHomeRecentResultSymbol = ordinaryHomeCurrentSymbol === "待输入" ? "" : `${ordinaryHomeCurrentSymbol} `;
  const ordinaryHomeExplainableSource = dailyCommandP3OneGlanceProviderVerified ? "来源已接上" : "来源待确认";
  const ordinaryHomeExplainableGap = dailyCommandP3ExplainableMissingEvidenceCount
    ? `仍有 ${String(dailyCommandP3ExplainableMissingEvidenceCount)} 项待补`
    : "暂无额外缺口";
  const ordinaryHomeExplainableResult = `${ordinaryHomeRecentResultSymbol}可解释：${ordinaryHomeExplainableSource}，${ordinaryHomeExplainableGap}；${ordinaryHomeLocalData}`;
  const ordinaryHomeStoragePromotionInline = ordinaryHomeReadableResultReady
    ? `；Storage 提升任务 ${String(
        storageCurrentResult.source_atomic_task_id ??
          candidateQuantResultVersionSummary.current_result_task_id ??
          candidateQuantResultVersionSummary.latest_task_id ??
          candidateQuantResultLineage.task_id ??
          "等待任务"
      )}`
    : "";
  const ordinaryHomeResultVersionGuardInline = ordinaryHomeReadableResultReady
    ? `；覆盖保护：${dailyCommandResultVersionGuardLabel}`
    : "";
  const ordinaryHomeLatestTushareTaskInline = latestTushareTaskSummary.taskId
    ? `；真实数据任务 ${latestTushareTaskSummary.taskId} / ${latestTushareTaskSummary.dataDate || "等待日期"} / ${String(latestTushareTaskSummary.rowCount)} 行 / scope ${latestTushareTaskSummary.scopeHashShort || "等待"}`
    : "";
  const ordinaryHomeRecentResult = dailyCommandP3OneGlanceReadable
    ? `${ordinaryHomeExplainableResult}${ordinaryHomeCanonicalResultInline}${ordinaryHomeStorageCurrentInline}${ordinaryHomeStoragePromotionInline}${ordinaryHomeLatestTushareTaskInline}${ordinaryHomeResultVersionGuardInline}`
    : ordinaryHomeStorageCurrentReadable
      ? `${ordinaryHomeStorageCurrentText}${ordinaryHomeStoragePromotionInline}${ordinaryHomeLatestTushareTaskInline}${ordinaryHomeResultVersionGuardInline}`
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? `${ordinaryHomeLocalData}，等待结论`
      : "暂无最近结果";
  const ordinaryHomeRecentResultState = dailyCommandP3OneGlanceReadable
    ? "结果可读"
    : ordinaryHomeStorageCurrentReadable
      ? "本地 current-result 可读"
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "写入中或待补"
      : dailyCommandHealthOk
        ? "等待确认"
        : "等待本地联通";
  const ordinaryHomeRecentResultSummary = dailyCommandP3OneGlanceReadable
    ? `${ordinaryHomeRecentResultSymbol || "当前标的 "}已有最近结果；先看来源、缺口和结果入口。`
    : ordinaryHomeStorageCurrentReadable
      ? `${ordinaryHomeStorageCurrentSymbol} 已有本地 current-result；先看来源、版本和结果入口。`
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "最近结果还在本地写入或降级回放中；先看任务进度、缺口和只读刷新。"
      : dailyCommandHealthOk
        ? "暂无最近结果；本地已接上，先输入股票；确认按钮会等 P0 证据完整后启用。"
        : "暂无最近结果；先恢复本地 FastAPI / bootstrap / desktop preflight / React 四段联通。";
  const ordinaryHomeRecentResultSource = dailyCommandP3OneGlanceReadable
    ? "CandidateRadar cache / Factor / Next 本地回放"
    : ordinaryHomeStorageCurrentReadable
      ? ordinaryHomeStorageCurrentSource
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "本地 task 回执 / cache 写入中"
      : dailyCommandHealthOk
        ? "本地只读入口已接上；等待确认或更完整证据"
        : "等待本地联通";
  const ordinaryHomeRecentResultGap = dailyCommandP3OneGlanceReadable
    ? ordinaryHomeExplainableGap
    : ordinaryHomeStorageCurrentReadable
      ? ordinaryHomeStorageCurrentGap
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "结论未完整回放；pending/degraded 仍要显示"
      : dailyCommandHealthOk
        ? "缺确认任务和本地结果；确认闸门等待 P0 证据"
        : "缺本地联通";
  const ordinaryHomePlainConclusionStatus = dailyCommandP3OneGlanceReadable
    ? "结果可读"
    : ordinaryHomeStorageCurrentReadable
      ? "本地结果可读"
    : dailyCommandLatestTaskStepLower.includes("blocked_")
      ? "被阻断或待补"
    : homeQuantVisibleTaskId || dailyCommandLatestTaskId || dailyCommandP2ThreeSurfaceReady
      ? "写入中或待补"
    : dailyCommandHealthOk
        ? "等待确认"
        : "等待本地联通";
  const ordinaryHomePlainConclusionText = dailyCommandP3OneGlanceReadable
    ? `${ordinaryHomeRecentResultSymbol || "当前标的 "}已有可读投研结果，先看来源和缺口，再看量化推演与次日图谱。`
    : ordinaryHomeStorageCurrentReadable
      ? `${ordinaryHomeStorageCurrentSymbol} 已有本地 current-result，版本 ${ordinaryHomeStorageCurrentVersion}，日期/新鲜度 ${ordinaryHomeStorageCurrentFreshnessLabel}；先看股票量化推演和次日图谱。`
    : dailyCommandLatestTaskStepLower.includes("blocked_")
      ? `最近确认被阻断或降级：${dailyCommandLatestConfirmReadableStatus}。`
      : homeQuantVisibleTaskId || dailyCommandLatestTaskId
        ? "最近确认已接收，结果还在本地回放或降级显示；先看任务进度。"
        : dailyCommandP2ThreeSurfaceReady
          ? "本地数据已回放，结论还没补齐；先刷新本地回放或看缺口。"
          : dailyCommandP0LocalReadinessReady
            ? "还没有确认记录；先输入股票并点击确认。"
            : dailyCommandHealthOk
              ? "本地已接上；可以看缓存和入口，确认按钮等待 P0 证据完整。"
            : "本地连接未 ready；先恢复 FastAPI / bootstrap / desktop preflight / React。";
  const ordinaryHomePlainConclusionMissing = dailyCommandP3OneGlanceReadable
    ? ordinaryHomeExplainableGap
    : ordinaryHomeStorageCurrentReadable
      ? ordinaryHomeStorageCurrentGap
    : dailyCommandLatestTaskStepLower.includes("blocked_")
      ? dailyCommandLatestConfirmReadableStatus
      : homeQuantVisibleTaskId || dailyCommandLatestTaskId || dailyCommandP2ThreeSurfaceReady
        ? homeQuantP1P2P3CheckpointLabel
        : dailyCommandHealthOk
          ? "缺确认任务和本地结果；确认闸门等待 P0 证据"
          : "缺本地联通";
  const ordinaryHomePlainConclusionNext = dailyCommandP3OneGlanceReadable
    ? "看股票量化推演，再看次日图谱"
    : ordinaryHomeStorageCurrentReadable
      ? "看股票量化推演，再看次日图谱"
    : dailyCommandLatestTaskStepLower.includes("blocked_")
      ? dailyCommandLatestConfirmNextAction
      : homeQuantVisibleTaskId || dailyCommandLatestTaskId || dailyCommandP2ThreeSurfaceReady
        ? "看任务进度，或只读刷新本地回放"
        : dailyCommandP0LocalReadinessReady
          ? "输入股票代码并确认"
          : dailyCommandHealthOk
            ? "本地已接上；先看当前标的和最近结果，等待确认闸门"
          : "打开桌面壳预检恢复本地连接";
  const ordinaryHomePlainConclusionTone: MetricItem["tone"] = dailyCommandP3OneGlanceReadable
    ? "good"
    : ordinaryHomeStorageCurrentReadable
      ? "good"
    : dailyCommandHealthOk || homeQuantVisibleTaskId || dailyCommandLatestTaskId || dailyCommandP2ThreeSurfaceReady
      ? "warn"
      : "neutral";
  const ordinaryHomeResultHint = ordinaryHomeReadableResultReady
    ? ordinaryHomeUserEditedNewSymbol ? "点击确认新标的" : homeQuantTaskId ? "刷新刚确认的结果" : "下一步看结果"
    : homeQuantTaskId || homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? ordinaryHomeUserEditedNewSymbol ? "点击确认新标的" : "稍后刷新本地回放，或先看股票量化推演"
      : dailyCommandP0LocalReadinessReady
        ? "输入股票代码并确认"
        : dailyCommandHealthOk
          ? "本地已接上；等待 P0 证据完整后确认股票"
        : "先恢复本地连接";
  const ordinaryHomeNextLabel = dailyCommandNeedsStartupRecovery
    ? "恢复本地连接"
    : ordinaryHomeUserEditedNewSymbol
      ? "确认股票"
    : homeQuantTaskId
      ? "刷新结果"
    : ordinaryHomeReadableResultReady
      ? "查看结果"
      : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
        ? "刷新结果"
      : "确认股票";
  const ordinaryHomeNextHref = dailyCommandNeedsStartupRecovery
    ? "#desktop"
    : ordinaryHomeReadableResultReady
      ? "#factor/factor-score"
      : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
        ? "#home"
        : dailyCommandHomeConfirmHref;
  const ordinaryHomeProgressHref = "#tasks";
  const ordinaryHomeConfirmTitle = homeQuantCanSubmit
    ? `确认 ${homeQuantSymbolValidation.normalized}`
    : homeQuantSymbol.trim()
      ? "修正代码后再确认"
      : "先输入股票代码";
  const ordinaryHomeRefreshTitle = homeQuantReadbackRefreshing
    ? "正在刷新本地结果"
    : "只刷新本地结果";
  const ordinaryHomeRecoveryTitle = "打开一键启动预检；按页面提示恢复本地连接";
  const ordinaryHomePrimaryActionKind = dailyCommandNeedsStartupRecovery
    ? "link"
    : ordinaryHomeUserEditedNewSymbol
      ? "confirm"
    : homeQuantTaskId
      ? "refresh"
    : ordinaryHomeReadableResultReady
      ? "link"
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "refresh"
      : "confirm";
  const ordinaryHomePrimaryActionDisabled = ordinaryHomePrimaryActionKind === "refresh"
    ? homeQuantReadbackRefreshing
    : ordinaryHomePrimaryActionKind === "confirm"
      ? !homeQuantCanSubmit
      : false;
  const ordinaryHomePrimaryActionTitle = ordinaryHomePrimaryActionKind === "refresh"
    ? ordinaryHomeRefreshTitle
    : ordinaryHomePrimaryActionKind === "confirm"
      ? ordinaryHomeConfirmTitle
      : dailyCommandNeedsStartupRecovery
        ? ordinaryHomeRecoveryTitle
      : ordinaryHomeReadableResultReady
        ? "只切换到结果入口：先看股票量化推演，再打开次日图谱；不会重新确认、不会刷新外部数据"
        : ordinaryHomeResultHint;
  const ordinaryHomePrimaryActionText = ordinaryHomePrimaryActionKind === "refresh" && homeQuantReadbackRefreshing
    ? "刷新中..."
    : ordinaryHomePrimaryActionKind === "confirm" && homeQuantSubmitting
      ? "确认中..."
      : ordinaryHomeNextLabel;
  const ordinaryHomeRecoveryAuditNote =
    "一键启动排障补充：失败时先运行 scripts/check_command_center_3.command 做 check-only 安全自检，不启动服务、不外联。";
  const ordinaryHomeConfirmStatusLine = homeQuantSubmitting
    ? "确认中：正在启动本地数据链，稍后自动回读结果。"
    : homeQuantSubmitError
      ? "确认失败：请先检查本地连接，再重新确认。"
    : ordinaryHomeReadableResultReady
      ? "已有结果：可以直接查看股票量化推演和次日图谱。"
    : homeQuantTaskId || homeQuantVisibleTaskId
      ? "已确认：本地数据正在回读，稍后刷新结果。"
    : dailyCommandP2ThreeSurfaceReady
      ? "本地数据已齐：等待可解释结论刷新。"
    : dailyCommandP0LocalReadinessReady
      ? "准备就绪：输入股票代码后点击确认。"
      : dailyCommandHealthOk
        ? "只读可用：可以查看本地缓存、最近结果和入口；确认按钮仍等待 P0 四段证据。"
        : "待恢复：先把本地连接接上。";
  const ordinaryHomeStatusBadge = dailyCommandHealthOk
    ? "本地已接上"
    : dailyCommandP0ReadbackPending
      ? "本地读取中"
      : "待恢复";
  const ordinaryHomeP0Conclusion = dailyCommandP0LocalReadinessReady
    ? "可以用：本地四段已接上"
    : dailyCommandHealthOk
      ? "本地已接上：确认闸门等待 P0 证据"
      : "先恢复：本地四段还没全部 ready";
  const ordinaryHomeP0ActionLabel = dailyCommandP0LocalReadinessReady
    ? dailyCommandPrimaryActionLabel
    : dailyCommandHealthOk
      ? "先看当前标的和最近结果"
      : dailyCommandPrimaryActionLabel;
  const ordinaryHomeP1GateLabel = dailyCommandP0LocalReadinessReady
    ? "health、bootstrap、desktop preflight、React 四段 ready，可以确认股票代码"
    : dailyCommandHealthOk
      ? "本地只读入口已接上；确认按钮等待 bootstrap / preflight / P0 connection evidence"
      : "health、bootstrap、desktop preflight、React 四段 ready 后再确认股票代码";
  const ordinaryHomeResultRouteSummary = dailyCommandP3OneGlanceReadable
    ? "结果已可读：先看股票量化推演，再看次日图谱；需要换标的再回下一票雷达详情。"
    : ordinaryHomeStorageCurrentReadable
      ? "Storage current-result 已可读：先看股票量化推演，再看次日图谱；需要换标的再回下一票雷达详情。"
    : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
      ? "结果写入中：先看任务进度或只读刷新本地回放；缺口会继续显示，不把空结果当无风险。"
      : dailyCommandP0LocalReadinessReady
        ? "确认后结果会从这里去看：股票量化推演、次日图谱、下一票雷达详情。"
        : dailyCommandHealthOk
          ? "本地已接上；确认闸门等待 P0 证据完整，结果入口保持只读可见。"
        : dailyCommandP0ReadbackPending
          ? "本页已打开；本地状态正在回读，可以先输入股票代码，确认按钮会等本地闸门变绿。"
          : "本地连接恢复后，先确认股票代码，再看结果入口。";
  const ordinaryHomeStatusItems: MetricItem[] = [
    {
      label: "本地联通",
      value: dailyCommandHealthOk
        ? dailyCommandP0LocalReadinessReady
          ? "已接上；确认按钮可用"
          : "已接上；确认闸门待 P0 证据"
        : dailyCommandP0ReadbackPending
          ? "本页已打开；本地状态读取中"
          : "待恢复",
      tone: dailyCommandHealthOk ? "good" : "warn"
    },
    {
      label: "当前标的",
      value: ordinaryHomeCurrentSymbol,
      tone: ordinaryHomeCurrentSymbol === "待输入" ? "warn" : "good"
    },
    {
      label: "最近结果",
      value: ordinaryHomeRecentResult,
      tone: ordinaryHomeReadableResultReady ? "good" : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady ? "warn" : "neutral"
    },
    {
      label: "下一步",
      value: ordinaryHomePlainConclusionNext,
      tone: dailyCommandP0LocalReadinessReady || ordinaryHomeReadableResultReady ? "good" : "warn"
    }
  ];
  const ordinaryHomeMarketSessionItems: MetricItem[] = [
    {
      label: "数据日期",
      value: ordinaryHomeDataDate || "待确认",
      tone: ordinaryHomeDataDate ? "good" : "warn"
    },
    {
      label: "当前 as-of",
      value: ordinaryHomeAsOfDate || ordinaryHomeExpectedTradeDate || "待确认",
      tone: ordinaryHomeAsOfDate || ordinaryHomeExpectedTradeDate ? "good" : "warn"
    },
    {
      label: "交易日历",
      value: ordinaryHomeCalendarValidated ? "已验证" : "未验证",
      tone: ordinaryHomeCalendarValidated ? "good" : "warn"
    },
    {
      label: "数据新鲜度",
      value: ordinaryHomeFreshnessLabel,
      tone: ordinaryHomeFreshnessIsFresh ? "good" : "warn"
    },
    {
      label: "缓存年龄",
      value: ordinaryHomeFreshnessAgeDays ? `${ordinaryHomeFreshnessAgeDays} 天` : "待确认",
      tone: ordinaryHomeFreshnessAgeDays ? "neutral" : "warn"
    }
  ];
  const ordinaryHomeAppVisibleNowSentence = dailyCommandP3OneGlanceReadable
      ? `打开 app 能看到 ${dailyCommandConfirmedSymbolLabel} 的最近投研结果：${ordinaryHomeExplainableResultLabel}；结果版本 ${dailyCommandCurrentResultVersion || "等待 result_version"}；下一步看股票量化推演和次日图谱。`
    : ordinaryHomeStorageCurrentReadable
      ? `打开 app 能看到 ${ordinaryHomeStorageCurrentSymbol} 的本地 current-result：${ordinaryHomeStorageCurrentVersion} / ${ordinaryHomeStorageCurrentFreshnessLabel}；下一步看股票量化推演和次日图谱。`
    : dailyCommandP0LocalReadinessReady
      ? "打开 app 能看到本地已接上、股票确认入口和等待结果状态；先输入股票代码并点击确认。"
      : dailyCommandHealthOk
        ? "打开 app 能看到只读入口已接上：可以看当前标的、最近结果、数据能力和下一步入口；确认按钮仍等待 P0 四段证据。"
        : dailyCommandP0ReadbackPending
          ? "打开 app 能看到首页已打开，本地状态正在回读；可以先输入股票代码，确认按钮会等本地闸门变绿。"
        : "打开 app 能看到本地连接待恢复：先看桌面壳预检，等 FastAPI、bootstrap、desktop preflight 和 React 变绿。";
  const ordinaryHomeRouteHealthLabel = userRouteQaLatestPassed
    ? `路线健康：${userRouteQaCoveredRoutes.length}/5 条普通入口已通过 ${userRouteQaCoveredViewports.join(" / ") || "本地 QA"}；输入静默。`
    : userRouteQaEvidence.latest_report_is_current_evidence === true
      ? `路线健康待复核：${homeText(userRouteQaEvidence.latest_report_status, "pending")}。`
      : "路线健康等待本地 QA；普通入口仍可只读使用。";
  const ordinaryHomeAppVisibleNowItems: MetricItem[] = [
    {
      label: "打开可见",
      value: ordinaryHomeAppVisibleNowSentence,
      tone: ordinaryHomeReadableResultReady || dailyCommandP0LocalReadinessReady ? "good" : "warn"
    },
    {
      label: "本地联通",
      value: dailyCommandP0LocalReadinessReady
        ? "FastAPI / bootstrap / desktop preflight / React 已接上"
        : dailyCommandHealthOk
          ? "只读入口已接上；确认按钮等待 P0 四段证据"
          : "等待四段本地联通",
      tone: dailyCommandHealthOk ? "good" : "warn"
    },
    {
      label: "当前标的",
      value: ordinaryHomeCurrentSymbol,
      tone: ordinaryHomeCurrentSymbol === "待输入" ? "warn" : "good"
    },
    {
      label: "最近结果",
      value: ordinaryHomeRecentResult,
      tone: ordinaryHomeReadableResultReady ? "good" : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady ? "warn" : "neutral"
    },
    {
      label: "本地 current-result",
      value: ordinaryHomeStorageCurrentText,
      tone: ordinaryHomeStorageCurrentReadable ? "good" : "warn"
    },
    {
      label: "日期/新鲜度",
      value: ordinaryHomeStorageCurrentFreshnessLabel,
      tone: ordinaryHomeStorageCurrentDataDate && ordinaryHomeStorageCurrentFreshness ? "good" : "warn"
    },
    {
      label: "最近真实数据任务",
      value: dailyCommandTushareLatestTaskLabel,
      tone: latestTushareTaskSummary.ready ? "good" : "warn"
    },
    {
      label: "真实数据 scope",
      value: dailyCommandTushareLatestScopeLabel,
      tone: latestTushareTaskSummary.scopeHashShort ? "good" : "warn"
    },
    {
      label: "来源层",
      value: ordinaryHomeRecentResultSource,
      tone: ordinaryHomeReadableResultReady || homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "明确缺口",
      value: ordinaryHomeRecentResultGap,
      tone: dailyCommandP3OneGlanceReadable && ordinaryHomeRecentResultGap === "暂无额外缺口" ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: dataCapabilityTushareRestrictedCount || dataCapabilityTusharePendingCount
        ? "本地数据能力待补；需要授权后再做真实补证"
        : dailyCommandTushareFirstLedgerReady || dataCapabilityTushareAvailableCount
          ? "本地数据能力可读；继续看结果来源和缺口"
          : "等待本地数据能力回放",
      tone: dataCapabilityTushareRestrictedCount || dataCapabilityTusharePendingCount ? "warn" : dailyCommandTushareFirstLedgerReady || dataCapabilityTushareAvailableCount ? "good" : "warn"
    },
    {
      label: "数据能力模式",
      value: dataCapabilityCache.cache_only === false ? "需复核：不是只读模式" : "只读本地缓存",
      tone: dataCapabilityCache.cache_only === false ? "bad" : "good"
    },
    {
      label: "数据能力血缘",
      value: dataCapabilityEvidenceLedgerCount ? "已有本地调用记录可查" : "等待本地调用记录",
      tone: dataCapabilityEvidenceLedgerCount ? "good" : "warn"
    },
    {
      label: "数据能力缺口",
      value: "真实数据补证仍需单独授权；首页不会自动补调，也不会把缺口当作可交易结论",
      tone: "warn"
    },
    {
      label: "路线健康",
      value: ordinaryHomeRouteHealthLabel,
      tone: userRouteQaLatestPassed && userRouteQaTypingSilenceVerified && userRouteQaTaskSilenceFailedCount === 0 ? "good" : "warn"
    },
    {
      label: "下一步入口",
      value: ordinaryHomePlainConclusionNext,
      tone: ordinaryHomeReadableResultReady || dailyCommandP0LocalReadinessReady ? "good" : "warn"
    },
    {
      label: "安全说明",
      value: "页面打开、输入和本地链接只读；只有确认按钮启动确认流程；不调用外部服务、不交易",
      tone: "good"
    }
  ];
  const ordinaryHomeRecentResultItems: MetricItem[] = [
    {
      label: "最近结果",
      value: ordinaryHomeRecentResult,
      tone: ordinaryHomeReadableResultReady ? "good" : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady ? "warn" : "neutral"
    },
    {
      label: "本地 current-result",
      value: ordinaryHomeStorageCurrentText,
      tone: ordinaryHomeStorageCurrentReadable ? "good" : "warn"
    },
    {
      label: "日期/新鲜度",
      value: ordinaryHomeStorageCurrentFreshnessLabel,
      tone: ordinaryHomeStorageCurrentDataDate && ordinaryHomeStorageCurrentFreshness ? "good" : "warn"
    },
    {
      label: "Storage 提升任务",
      value: ordinaryHomeStoragePromotionInline || "等待 Storage 提升任务",
      tone: ordinaryHomeReadableResultReady ? "good" : "warn"
    },
    {
      label: "覆盖保护",
      value: dailyCommandResultVersionGuardLabel,
      tone: dailyCommandResultVersionGuardReady ? "good" : "warn"
    },
    {
      label: "状态",
      value: ordinaryHomeRecentResultState,
      tone: ordinaryHomeReadableResultReady ? "good" : dailyCommandP0LocalReadinessReady ? "warn" : "neutral"
    },
    {
      label: "来源",
      value: ordinaryHomeRecentResultSource,
      tone: ordinaryHomeReadableResultReady || homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "缺口/degraded",
      value: ordinaryHomeRecentResultGap,
      tone: dailyCommandP3OneGlanceReadable && !dailyCommandP3ExplainableMissingEvidenceCount ? "good" : "warn"
    },
    {
      label: "现在做什么",
      value: ordinaryHomeResultHint,
      tone: dailyCommandP0LocalReadinessReady || ordinaryHomeReadableResultReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读最近本地结果记录；不创建第二个任务，不把空结果当无风险",
      tone: "good"
    }
  ];
  const ordinaryHomePlainConclusionItems: MetricItem[] = [
    {
      label: "一句话结论",
      value: ordinaryHomePlainConclusionText,
      tone: ordinaryHomePlainConclusionTone
    },
    {
      label: "结果状态",
      value: ordinaryHomePlainConclusionStatus,
      tone: ordinaryHomePlainConclusionTone
    },
    {
      label: "缺口",
      value: ordinaryHomePlainConclusionMissing,
      tone: dailyCommandP3OneGlanceReadable && !dailyCommandP3ExplainableMissingEvidenceCount ? "good" : "warn"
    },
    {
      label: "现在做什么",
      value: ordinaryHomePlainConclusionNext,
      tone: dailyCommandP0LocalReadinessReady || ordinaryHomeReadableResultReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读本地最近任务和结果；不创建 task、不调用 provider/model、不交易",
      tone: "good"
    }
  ];
  const ordinaryHomeResultRouteItems: MetricItem[] = [
    {
      label: "确认后去哪看",
      value: ordinaryHomeResultRouteSummary,
      tone: dailyCommandP3OneGlanceReadable ? "good" : dailyCommandP0LocalReadinessReady ? "warn" : "neutral"
    },
    {
      label: "结果入口",
      value: "股票量化推演 / 次日图谱 / 下一票雷达详情",
      tone: "good"
    },
    {
      label: "降级读法",
      value: dailyCommandP3OneGlanceReadable
        ? "已有可读结论；继续看来源和缺口"
        : homeQuantVisibleTaskId || dailyCommandP2ThreeSurfaceReady
          ? "本地写入中；缺数据会显示 pending / 缺少证据"
          : "暂无结果不等于无风险；先确认股票",
      tone: dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "安全说明",
      value: "结果路标只切换本地页面；不新建任务、不调用外部服务或模型、不交易",
      tone: "good"
    }
  ];
  const homeQuantReadbackRefreshLabel = homeQuantReadbackRefreshing
    ? "正在回读 CandidateRadar / Factor / Next / Tasks"
    : homeQuantReadbackLastRefresh
      ? `最近回读 ${homeQuantReadbackLastRefresh}`
      : "等待确认按钮后的本地回读";
  const homeQuantManualReadbackButtonLabel = homeQuantReadbackRefreshing
    ? "正在只读刷新本地回放"
    : "只读刷新本地回放";
  const homeQuantManualReadbackBoundary =
    "只重新读取 CandidateRadar / Factor / Next / Tasks 本地 GET cache；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不交易";
  const homeQuantConfirmItems: MetricItem[] = [
    { label: "输入代码", value: homeQuantSymbolValidation.valid ? homeQuantSymbolValidation.normalized : homeQuantSubmitDisabledReason, tone: homeQuantSymbolValidation.valid ? "good" : "warn" },
    { label: "确认按钮", value: homeQuantCanSubmit ? `可点击：${homeQuantSymbolValidation.normalized} 将创建 Tushare-first POST task` : `不可点击：${homeQuantSubmitDisabledReason}`, tone: homeQuantCanSubmit ? "good" : "warn" },
    { label: "P0 闸门", value: dailyCommandP0LocalReadinessReady ? "ready：可点击确认" : "check：先恢复本地联通", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
    { label: "P1 手动确认", value: homeP1ManualConfirmLabel, tone: homeP1ManualConfirmReady ? "good" : "warn" },
    { label: "任务状态", value: homeQuantReadbackStatus, tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "回读刷新", value: homeQuantReadbackRefreshLabel, tone: homeQuantReadbackRefreshing || homeQuantReadbackLastRefresh ? "good" : "warn" },
    { label: "本地回放", value: homeQuantP1P2P3CheckpointLabel, tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
    { label: "Tushare-first", value: "确认按钮才 POST；模型解释单独补证，成功后通过 GET cache 回放", tone: "good" },
    { label: "P2/P3 回放", value: dailyCommandSmallDataWritebackState, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
    { label: "边界", value: "首页输入静默；不从页面打开、输入、React render 或 GET cache 外联；不交易、不改交易策略", tone: "good" }
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
      当前状态: homeP1ManualConfirmReady ? "点击后创建 Tushare-first POST task" : "等待按钮链路 ready",
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
      当前状态: dailyCommandP2ThreeSurfaceReady ? "P2/P3 已从 cache / call_ledger / packet 回放" : "等待任务写入本地三面",
      用户下一步: "看股票量化推演、次日图谱和下一票雷达详情",
      证据: "CandidateRadar cache / call_ledger / packet",
      边界: "回放不创建第二个 task、不补调 provider/model、不读取敏感凭据。"
    }
  ];
  const homeQuantPostConfirmNextStepLabel = dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable
    ? "已进入回放：先看股票量化推演，再打开次日图谱；需要换标的再点确认"
    : homeQuantVisibleTaskId
      ? "先看任务进度；success 后刷新本地回放"
      : "先输入股票代码并点击确认按钮";
  const homeQuantPostConfirmStageLabel = homeQuantSubmitting
    ? "提交中：等待本地 task id"
    : homeQuantReadbackRefreshing
      ? "回读中：刷新下一票雷达、量化推演、次日图谱和任务目录"
      : homeQuantP1P2P3CheckpointReady
        ? "已回放：P1/P2/P3 可读"
        : homeQuantVisibleTaskCanPoll
          ? `进度中：${dailyCommandLatestConfirmReadableStatus}`
          : homeQuantVisibleTaskId
            ? `已接收：${dailyCommandLatestConfirmReadableStatus}`
            : "未开始：等待确认按钮";
  const homeQuantPostConfirmStageNext = homeQuantP1P2P3CheckpointReady
    ? "任务编号出现或从本地 cache 恢复后，先看任务进度；成功后按股票量化推演和次日图谱回放；换标的再手动确认"
    : homeQuantVisibleTaskId
      ? homeQuantPostConfirmNextStepLabel
      : "输入股票代码后点击确认按钮；输入本身不创建 task";
  const homeQuantPostConfirmLocalProgressItems: MetricItem[] = [
    {
      label: "确认后阶段",
      value: homeQuantPostConfirmStageLabel,
      tone: homeQuantP1P2P3CheckpointReady || homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "同一链路",
      value: homeQuantVisibleTaskId
        ? `${dailyCommandConfirmedSymbolLabel} / ${homeQuantVisibleTaskId}`
        : "等待确认按钮返回回执",
      tone: homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "三面结果",
      value: dailyCommandP2ThreeSurfaceReady && dailyCommandP3OneGlanceReadable
        ? "P2 三面与 P3 结论同源回放"
        : dailyCommandP2ThreeSurfaceReady
          ? "P2 三面已回放，P3 结论等待刷新"
          : "等待数据写入三面回放",
      tone: dailyCommandP2ThreeSurfaceReady && dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "回放入口",
      value: dailyCommandP3OneGlanceReadable
        ? "股票量化推演和次日图谱按同一次确认打开"
        : "任务 success 后刷新，再看股票量化推演和次日图谱",
      tone: dailyCommandP3OneGlanceReadable ? "good" : "warn"
    }
  ];
  const homeQuantPostConfirmBackendItems: MetricItem[] = candidateQuantPostConfirmOneGlanceRows.length
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
        { label: "确认回执", value: homeQuantVisibleTaskId || "等待确认按钮返回回执", tone: homeQuantVisibleTaskId ? "good" : "warn" },
        { label: "确认来源", value: homeQuantVisibleTaskSource, tone: homeQuantVisibleTaskId ? "good" : "warn" },
        { label: "确认后阶段", value: homeQuantPostConfirmStageLabel, tone: homeQuantVisibleTaskId || homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
        { label: "先看哪里", value: homeQuantPostConfirmNextStepLabel, tone: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable ? "good" : "warn" },
        { label: "数据写入", value: "三面结果回放", tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
        { label: "P3 结果", value: "股票量化推演 + 次日图谱 + 下一票雷达详情", tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
        { label: "DeepSeek", value: "单独治理，不阻塞当前结果", tone: "good" },
        { label: "安全边界", value: "回放不重复启动确认链，不下单，不改交易策略", tone: "good" }
      ];
  const homeQuantPostConfirmOneGlanceItems: MetricItem[] = [
    ...homeQuantPostConfirmBackendItems,
    ...homeQuantPostConfirmLocalProgressItems
  ];
  const homeQuantPostConfirmReadableSentence = homeQuantVisibleTaskId
    ? `${homeQuantPostConfirmStageLabel}；已拿到确认回执 ${homeQuantVisibleTaskId}（${homeQuantVisibleTaskSource}）；${dailyCommandP2ThreeSurfaceReady ? "P2 三面已可读" : "P2 三面等待本地回放"}；${dailyCommandP3OneGlanceReadable ? `P3 结论：${dailyCommandExplainableResultLabel}` : "P3 结论等待本地结果回放"}；下一步：${homeQuantPostConfirmStageNext}。`
    : `${homeQuantPostConfirmStageLabel}；确认后会在这里显示确认回执、P2 三面、P3 结论和下一步入口。`;
  const ordinaryHomePostConfirmItems: MetricItem[] = [
    {
      label: "确认回执",
      value: homeQuantVisibleTaskId || "点击确认后显示本地回执编号",
      tone: homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "任务进度",
      value: homeQuantVisibleTaskId ? dailyCommandLatestConfirmReadableStatus : "等待确认按钮",
      tone: homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "本地回放",
      value: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable
        ? homeQuantP1P2P3CheckpointLabel
        : "确认后回读 CandidateRadar / Factor / Next / Tasks",
      tone: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "下一步",
      value: homeQuantPostConfirmStageNext,
      tone: homeQuantVisibleTaskId || dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "安全说明",
      value: "这张状态只读本地任务和缓存；不重复确认、不调用模型、不交易",
      tone: "good"
    }
  ];
  const ordinaryHomeConfirmResultChainSentence = dailyCommandP3OneGlanceReadable
    ? `${dailyCommandConfirmedSymbolLabel} 已有结果链路：确认已接收，进度已可看，本地记录可回放，结果入口已指向量化推演和次日图谱。`
    : homeQuantVisibleTaskId || homeQuantTaskId || dailyCommandP2ThreeSurfaceReady
      ? "确认后结果链路正在回放：先看进度，再看本地记录，最后进入量化推演或次日图谱。"
      : dailyCommandP0LocalReadinessReady
        ? "确认后结果链路等待开始：先输入股票并点击确认，随后按进度、本地记录、结果入口顺序看。"
        : "确认后结果链路暂停：先恢复本地连接，再回首页确认股票。";
  const ordinaryHomeConfirmResultChainItems: MetricItem[] = [
    {
      label: "1. 确认接收",
      value: homeQuantVisibleTaskId || homeQuantTaskId
        ? "已接收确认"
        : dailyCommandP0LocalReadinessReady
          ? "等待点击确认"
          : "等待本地连接",
      tone: homeQuantVisibleTaskId || homeQuantTaskId ? "good" : "warn"
    },
    {
      label: "2. 进度",
      value: homeQuantPostConfirmStageLabel,
      tone: homeQuantVisibleTaskId || homeQuantP1P2P3CheckpointReady ? "good" : "warn"
    },
    {
      label: "3. 本地记录",
      value: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable
        ? "可回放"
        : homeQuantVisibleTaskId || homeQuantTaskId
          ? "写入中或降级显示"
          : "等待确认",
      tone: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "4. 结果入口",
      value: dailyCommandP3OneGlanceReadable
        ? "可看量化推演和次日图谱"
        : "等待结果后进入量化推演/次日图谱",
      tone: dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "安全说明",
      value: "只读当前结果链；普通链接只切换本地页面；不调用外部服务、不交易、不改策略",
      tone: "good"
    }
  ];
  const ordinaryHomePostConfirmReplaySummary = homeQuantVisibleTaskId
    ? `确认回执 ${homeQuantVisibleTaskId} 已可读；${homeQuantP1P2P3CheckpointLabel}；下一步看股票量化推演 / 次日图谱。`
    : dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable
      ? `本地已有回放；${homeQuantP1P2P3CheckpointLabel}；先看结果入口，换标的再确认。`
      : dailyCommandP0LocalReadinessReady
        ? "点击确认后，这里会压缩显示回执、进度、本地结果、结果入口和 degraded 状态。"
        : "本地连接恢复后，确认按钮返回的回放状态会显示在这里。";
  const ordinaryHomePostConfirmReplayItems: MetricItem[] = [
    {
      label: "回执",
      value: homeQuantVisibleTaskId || "等待确认按钮返回本地回执",
      tone: homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "进度",
      value: homeQuantVisibleTaskId ? dailyCommandLatestConfirmReadableStatus : "点击确认后显示任务进度",
      tone: homeQuantVisibleTaskId ? "good" : "warn"
    },
    {
      label: "本地结果",
      value: homeQuantP1P2P3CheckpointLabel,
      tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn"
    },
    {
      label: "结果入口",
      value: dailyCommandP3OneGlanceReadable
        ? "股票量化推演 / 次日图谱可看"
        : dailyCommandP2ThreeSurfaceReady
          ? "先刷新结论，再看股票量化推演 / 次日图谱"
          : "等待本地回放后再看",
      tone: dailyCommandP3OneGlanceReadable || dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "degraded",
      value: dailyCommandP3OneGlanceReadable && !dailyCommandP3ExplainableMissingEvidenceCount
        ? "未标记 degraded"
        : "缺结果时继续显示 pending/degraded",
      tone: dailyCommandP3OneGlanceReadable && !dailyCommandP3ExplainableMissingEvidenceCount ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读确认后的本地回放；不重复确认、不补调 provider/model、不交易",
      tone: "good"
    }
  ];
  const ordinaryHomePostConfirmReplayPrimaryHref = dailyCommandP3OneGlanceReadable
    ? "#factor/factor-score"
    : homeQuantVisibleTaskId || dailyCommandLatestTaskId
      ? ordinaryHomeProgressHref
      : dailyCommandCandidateConfirmHref;
  const ordinaryHomePostConfirmReplayPrimaryLabel = dailyCommandP3OneGlanceReadable
    ? "看股票量化推演"
    : homeQuantVisibleTaskId || dailyCommandLatestTaskId
      ? "看确认进度"
      : "先确认股票";
  const ordinaryHomePostConfirmReplayActionNote = dailyCommandP3OneGlanceReadable
    ? "结果已可读：先看量化推演，再看次日图谱；需要换标的再回确认输入区。"
    : homeQuantVisibleTaskId || dailyCommandLatestTaskId
      ? "已有本地确认记录：先看任务进度，成功后刷新本地回放并进入结果入口。"
      : "暂无确认记录：先输入股票并点击确认；输入本身保持静默。";
  const homeQuantResultRouteReady = dailyCommandP3OneGlanceReadable || dailyCommandP2ThreeSurfaceReady;
  const homeQuantResultRouteSentence = homeQuantResultRouteReady
    ? `${dailyCommandConfirmedSymbolLabel} 结果路标：先读 P3 结论，再看股票量化推演支持/压制，最后打开次日图谱；换标的仍回确认输入区。`
    : "结果路标：确认前先看按钮说明；确认后按任务进度、P2 三面、P3 结论、股票量化推演、次日图谱顺序读。";
  const homeQuantResultRouteBoundary =
    "结果路标只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不交易、不改交易策略";
  const homeQuantResultRouteItems: MetricItem[] = [
    { label: "当前结果", value: dailyCommandP3OneGlanceReadable ? dailyCommandExplainableResultLabel : homeQuantPostConfirmStageLabel, tone: homeQuantResultRouteReady ? "good" : "warn" },
    { label: "先看哪里", value: dailyCommandP3OneGlanceReadable ? "股票量化推演支持/压制" : "任务进度和 P2 三面写回", tone: homeQuantResultRouteReady ? "good" : "warn" },
    { label: "图谱", value: dailyCommandNextSessionReadableStatus, tone: dailyCommandNextSessionTone },
    { label: "换标的", value: "回确认输入区；输入静默，确认按钮才创建 Tushare-first task", tone: "good" },
    { label: "边界", value: homeQuantResultRouteBoundary, tone: "good" }
  ];
  const homeQuantPostConfirmReadbackState = homeQuantSubmitting
    ? "提交中：等待本地后端返回确认回执；不会重复创建第二次确认。"
    : homeQuantReadbackRefreshing
      ? "确认已接收：正在回读下一票雷达、股票量化推演、次日图谱和任务目录；这只是本地结果回读。"
    : homeQuantVisibleTaskCanPoll
      ? "确认已接收：本地进度面板正在等待完成，成功后自动刷新下一票雷达、量化推演、次日图谱和任务目录。"
      : homeQuantVisibleTaskId
        ? "最近确认链来自本地回放；首页不重复启动进度面板，也不创建第二次确认。"
        : "确认后首页会回读下一票雷达、股票量化推演、次日图谱和任务目录；输入代码本身保持静默。";
  const homeQuantImmediateReceiptSentence = homeQuantSubmitting
    ? "正在提交：等待本地后端返回 task id；按钮临时禁用，避免重复点击。"
    : homeQuantSubmitError
      ? `确认未完成：${homeQuantSubmitError}；先复核 P0 四段，再由用户手动重试。`
      : homeQuantTaskPanelTaskId
        ? `本次确认已接收：task=${homeQuantTaskPanelTaskId}；下方任务进度会等待 success，成功后自动回读 CandidateRadar / Factor / Next / Tasks。`
        : homeQuantRecoveredTaskId
          ? `已有最近确认回放：task=${homeQuantRecoveredTaskId}；这是本地 cache 回放，不会重新启动进度面板。`
          : "点击确认后这里立即显示 task id、下一步和安全边界；输入本身保持静默。";
  const homeQuantImmediateReceiptItems: MetricItem[] = [
    {
      label: "本次确认回执",
      value: homeQuantSubmitting
        ? "提交中，等待 task id"
        : homeQuantTaskPanelTaskId
          ? `已接收 ${homeQuantTaskPanelTaskId}`
          : homeQuantSubmitError
            ? "未创建，先看恢复提示"
            : homeQuantRecoveredTaskId
              ? `最近回放 ${homeQuantRecoveredTaskId}`
              : "等待确认按钮",
      tone: homeQuantTaskPanelTaskId || homeQuantRecoveredTaskId ? "good" : homeQuantSubmitError ? "bad" : "warn"
    },
    {
      label: "确认来源",
      value: homeQuantTaskPanelTaskId
        ? "本次首页确认按钮"
        : homeQuantRecoveredTaskId
          ? homeQuantVisibleTaskSource
          : "等待用户点击确认",
      tone: homeQuantTaskPanelTaskId || homeQuantRecoveredTaskId ? "good" : "warn"
    },
    {
      label: "下一步",
      value: homeQuantTaskPanelTaskId
        ? "看任务进度；success 后自动回读三面"
        : homeQuantRecoveredTaskId
          ? "按最近确认链只读回放；换标的再手动确认"
          : "输入代码后点击确认按钮",
      tone: homeQuantTaskPanelTaskId || homeQuantRecoveredTaskId ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只有再次显式点击才会创建新的确认 task；不自动调用 DeepSeek、不下单、不改交易策略",
      tone: "good"
    }
  ];
  const homeQuantSubmitFailureRecoveryRows = [
    {
      恢复项: "1. 失败先停住",
      当前状态: homeQuantSubmitError ? "确认任务未创建或未返回 task id" : "等待确认按钮",
      用户下一步: homeQuantSubmitError ? "先不要重复点击；确认 P0 四段仍为 ready" : "输入代码后点击确认按钮",
      入口: "#home-p1-symbol-confirm",
      边界: "失败提示不自动重试、不创建第二个 task、不调用 Tushare/DeepSeek。"
    },
    {
      恢复项: "2. 回看 P0",
      当前状态: dailyCommandP0LocalReadinessReady ? "P0 ready" : "P0 check",
      用户下一步: dailyCommandP0LocalReadinessReady ? "可手动重新确认一次" : "先打开一键启动预检恢复本地四段联通",
      入口: "#desktop",
      边界: "只切换本地预检页；不启动服务、不外联、不写 cache。"
    },
    {
      恢复项: "3. 手动重试",
      当前状态: homeQuantCanSubmit ? `可重试：${homeQuantSymbolValidation.normalized}` : homeQuantSubmitDisabledReason,
      用户下一步: "修正输入或恢复 P0 后，再由用户手动点击确认按钮",
      入口: "确认股票并启动数据链",
      边界: "只有下一次显式点击才会创建新的 Tushare-first POST task；DeepSeek 仍 skipped/governed。"
    }
  ];
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
      当前状态: dailyCommandP2ThreeSurfaceReady ? "P2/P3 本地回放已可读" : "等待确认结果写入本地三面",
      用户下一步: "打开股票量化推演，复核支持/压制和 P3 可读结论",
      入口: "#factor",
      边界: "链接只切换本地模块；Factor 页 GET cache 不补调 Tushare/DeepSeek。"
    },
    {
      交接项: "次日图谱",
      当前状态: dailyCommandNextSessionReadableStatus,
      用户下一步: "打开次日图谱，复核路径、参考线和 operation_zones",
      入口: "#next",
      边界: "operation_zones 只是复核区间；不是买卖、下单或 strategy action。"
    },
    {
      交接项: "下一票雷达结果",
      当前状态: dailyCommandP3OneGlanceReadable ? "P3 可解释结果可回放" : "等待下一票雷达结果检查点",
      用户下一步: "需要换标的时回下一票雷达确认输入区；输入仍保持静默，确认按钮才创建 task",
      入口: "#candidates/candidate-radar-search-quant-projection",
      边界: "结果回放只读 CandidateRadar cache / ledger / packet；不调用模型；结果回放只读下一票雷达本地三面结果。"
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
      边界: "页面打开、React render 和 GET cache 只读；不启动服务、不外联、不读取 token/key；敏感凭据也不读取"
    },
    {
      阶段: "P1 确认按钮触发 Tushare-first",
      当前状态: dailyCommandTushareFirstLedgerReady
        ? `${dailyCommandTushareFirstLedgerLabel}；task=${homeQuantVisibleTaskId || dailyCommandP3OneGlanceSourceTask}`
        : homeQuantVisibleTaskId
          ? `确认任务已可见：${homeQuantVisibleTaskId}；等待 Tushare-first ledger 回放`
          : "等待用户在首页或下一票雷达输入代码并点击确认",
      用户下一步: dailyCommandTushareFirstLedgerReady
        ? "直接看 P2 小数据三面和 P3 可解释结果；新标的再点确认按钮"
        : homeQuantVisibleTaskId
          ? "等待 TaskStatusPanel success 后刷新本地 cache / ledger / packet"
          : "输入 6 位 A 股代码，点击“确认股票并启动数据链”",
      证据: dailyCommandTushareFirstLedgerReady
        ? "CandidateRadar small_data_writeback_summary + source task call_ledger"
        : "CandidateRadar 搜票确认 POST task contract",
      边界: "搜索输入只做本地校验；只有确认按钮创建 POST task / worker，模型解释单独补证"
    },
    {
      阶段: "P2 小数据写入 cache / ledger / packet",
      当前状态: dailyCommandSmallDataWritebackState,
      用户下一步: "看 task id 和 TaskStatusPanel，成功后刷新本地 cache / ledger / packet 回放",
      证据: "ordinary_writeback_surface_summary_rows + call_ledger + packet",
      边界: "GET cache 只读回放；不补调 Tushare、DeepSeek，不展示敏感凭据或 raw log"
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
      当前状态: `re-entry gate visible；strict closeout ${dailyCommandP6StrictCloseoutState}`,
      用户下一步: dailyCommandP6NextEvidence,
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
      回归项: "1a. strict closeout 状态",
      当前状态: "re-entry gate visible；LTG closeout 未关闭",
      用户下一步: "保持 LTG closeout 关闭，后续按 direct evidence 补证",
      入口: "#migration",
      边界: "只读迁移状态，不关闭 LTG"
    },
    {
      回归项: "2. strict closeout 入口",
      当前状态: `只按 current-head direct evidence 关闭；当前 closeout=${dailyCommandP6StrictCloseoutState}；remaining=${String(dailyCommandP6StrictCloseoutRemaining)}`,
      用户下一步: dailyCommandP6NextEvidence,
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
  const dailyCommandResearchRouteMapItems: MetricItem[] = [
    {
      label: "1. 确认股票",
      value: dailyCommandP0LocalReadinessReady ? "首页确认卡可用；输入静默，确认按钮才创建 task" : "先恢复本地四段联通",
      tone: dailyCommandP0LocalReadinessReady ? "good" : "warn"
    },
    {
      label: "2. 候选复核",
      value: "下一票雷达看 Top / Watch / Excluded、来源、缺口和非买入边界",
      tone: Number(candidateCounts?.candidate_count ?? 0) ? "good" : "warn"
    },
    {
      label: "3. ETF/融资风险",
      value: "涉及 ETF、仓位或融资预算时去 ETF / 融资页看风险线",
      tone: "good"
    },
    {
      label: "4. 次日图谱",
      value: "确认后再看次日图谱；只读本地 operation map，不改交易策略",
      tone: next.status ? "good" : "warn"
    },
    {
      label: "边界",
      value: "这些路标只切换本地页面；不创建 task、不调用 provider/model、不交易",
      tone: "good"
    }
  ];
  const candidateHomeGroupCount = (group: string) =>
    candidateTopWatchExcludedRows.filter((row) => String(row.group ?? "").toLowerCase() === group).length;
  const ordinaryHomeCandidateTopCount =
    Number(candidateCoarseFineScreening.top_count ?? 0) ||
    candidateHomeGroupCount("top") ||
    candidateHomeRows.length ||
    Number(candidateCounts?.candidate_count ?? 0);
  const ordinaryHomeCandidateWatchCount =
    Number(candidateCoarseFineScreening.watch_count ?? 0) ||
    candidateHomeGroupCount("watch");
  const ordinaryHomeCandidateExcludedCount =
    Number(candidateCoarseFineScreening.excluded_count ?? 0) ||
    candidateHomeGroupCount("excluded");
  const ordinaryHomeCandidateGroupLabel =
    `Top ${String(ordinaryHomeCandidateTopCount)} / Watch ${String(ordinaryHomeCandidateWatchCount)} / Excluded ${String(ordinaryHomeCandidateExcludedCount)}`;
  const ordinaryHomeCandidateReadable =
    ordinaryHomeCandidateTopCount + ordinaryHomeCandidateWatchCount + ordinaryHomeCandidateExcludedCount > 0;
  const ordinaryHomeCandidateGapCount =
    Number(candidateCoarseFineScreening.gap_visible_count ?? 0) ||
    candidateTopWatchExcludedRows.filter((row) =>
      row.manual_review_required === true ||
      Number(row.data_gap_count ?? 0) > 0 ||
      Boolean(String(row.gap_summary ?? "").trim())
    ).length ||
    Number(candidateCounts?.missing_provider_data_group_count ?? 0);
  const ordinaryHomeCandidateSourceMode = String(
    candidateCoarseFineScreening.source_mode ??
      candidateScanExecutionSummary.cache_source ??
      (ordinaryHomeCandidateReadable ? "cache_only" : "empty_cache")
  );
  const ordinaryHomeCandidateSourceLabel =
    ordinaryHomeCandidateSourceMode === "tushare_backed_sample"
      ? "真实数据样本已回放；仍需看补证缺口"
      : ordinaryHomeCandidateSourceMode === "local_fallback"
        ? "本地 fallback：来自候选缓存或按钮门控记录"
        : ordinaryHomeCandidateSourceMode === "cache_only"
          ? "cache-only：只读本地候选缓存"
          : ordinaryHomeCandidateReadable
            ? `本地来源：${ordinaryHomeCandidateSourceMode}`
            : "empty cache：暂无候选";
  const ordinaryHomeCandidateGapLabel = ordinaryHomeCandidateGapCount
    ? `可见缺口 ${String(ordinaryHomeCandidateGapCount)} 项；先复核来源、理由和缺口`
    : "未标记候选池缺口";
  const ordinaryHomeCandidateCacheReadable = dailyCommandHealthOk || Boolean(candidates.status);
  const ordinaryHomeCandidateStatus = !ordinaryHomeCandidateCacheReadable
    ? "p0_check"
    : ordinaryHomeCandidateReadable
      ? ordinaryHomeCandidateGapCount || Number(candidateCounts?.degraded_mode_active_count ?? 0)
        ? "readable_degraded"
        : "readable"
      : "empty_cache";
  const ordinaryHomeCandidateReadableSentence =
    ordinaryHomeCandidateStatus === "readable"
      ? `下一票候选池可读：${ordinaryHomeCandidateGroupLabel}；先按分组复核，不当买入指令。`
      : ordinaryHomeCandidateStatus === "readable_degraded"
        ? `下一票候选池可读但有缺口：${ordinaryHomeCandidateGapLabel}；先复核来源和理由。`
        : ordinaryHomeCandidateStatus === "empty_cache"
          ? "下一票候选池暂无候选；先确认股票或打开候选池查看缺口。"
          : "下一票雷达缓存未完全接上；先恢复本地 FastAPI / cache。";
  const ordinaryHomeCandidateNext = ordinaryHomeCandidateStatus === "p0_check"
    ? "打开一键启动预检，恢复本地联通"
    : ordinaryHomeCandidateReadable
      ? "打开候选池，看 Top / Watch / Excluded，再决定是否对单票确认"
      : "先确认股票代码，或打开候选池查看空缓存原因";
  const ordinaryHomeCandidatePrimaryHref = ordinaryHomeCandidateStatus === "p0_check"
    ? "#desktop"
    : ordinaryHomeCandidateReadable
      ? "#candidates/candidate-pool"
      : dailyCommandCandidateConfirmHref;
  const ordinaryHomeCandidatePrimaryLabel = ordinaryHomeCandidateStatus === "p0_check"
    ? "恢复本地连接"
    : ordinaryHomeCandidateReadable
      ? "看候选池"
      : "先确认股票";
  const ordinaryHomeCandidatePreviewRows = (candidateTopWatchExcludedRows.length ? candidateTopWatchExcludedRows : candidateHomeRows)
    .slice(0, 5)
    .map((row, index) => ({
      序号: homeText(row.display_rank ?? row.rank, String(index + 1)),
      分组: homeText(row.group, "Top"),
      标的: homeText(row.ticker),
      名称: homeText(row.name),
      理由: homeText(row.reason ?? row.evidence_chain_summary, "等待候选理由"),
      来源: homeText(row.data_source ?? row.source ?? row.source_mode, ordinaryHomeCandidateSourceLabel),
      缺口: homeText(row.gap_summary, ordinaryHomeCandidateGapLabel),
      边界: "只供研究复核，不生成买入、卖出、加仓或融资指令"
    }));
  const ordinaryHomeCandidateRadarItems: MetricItem[] = [
    {
      label: "候选结论",
      value: ordinaryHomeCandidateReadableSentence,
      tone: ordinaryHomeCandidateStatus === "readable" ? "good" : ordinaryHomeCandidateStatus === "p0_check" ? "neutral" : "warn"
    },
    {
      label: "Top/Watch/Excluded",
      value: ordinaryHomeCandidateGroupLabel,
      tone: ordinaryHomeCandidateReadable ? "good" : "warn"
    },
    {
      label: "来源",
      value: ordinaryHomeCandidateSourceLabel,
      tone: ordinaryHomeCandidateReadable ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryHomeCandidateGapLabel,
      tone: ordinaryHomeCandidateGapCount ? "warn" : "good"
    },
    {
      label: "现在做什么",
      value: ordinaryHomeCandidateNext,
      tone: ordinaryHomeCandidateCacheReadable ? "good" : "warn"
    },
    {
      label: "ETF/融资提醒",
      value: "涉及 ETF、仓位或融资预算时，转去 ETF / 融资页看风险线",
      tone: "good"
    },
    {
      label: "非买入边界",
      value: "候选只表示复核顺序；不是买入、卖出、加仓或融资指令",
      tone: "good"
    }
  ];
  const homeEtfProviderRows = homeRows(homeEtfPacket.recommended_etfs).slice(0, 3);
  const homeEtfDataDate = homeText(homeEtfPacket.trade_date ?? homeEtfPacket.provider_data_date, "待补");
  const homeMarginDataDate = homeText(homeMarginPacket.trade_date ?? homeMarginPacket.provider_data_date, "待补");
  const homeMarginEtfAlignmentStatus = homeText(
    homeMarginEtfReceipt.margin_etf_data_alignment_status ?? homeEtfPacket.margin_etf_data_alignment_status,
    "not_bound"
  );
  const homeEtfReady = homeEtfPacket.status === "ready" && homeEtfProviderRows.length > 0;
  const homeMarginReady = homeMarginPacket.status === "ready";
  const homeMarginEtfSameResultBound = homeMarginEtfReceipt.margin_etf_same_result_bound === true;
  const homeYi = (value: unknown) => {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")} 亿` : "待补";
  };
  const homePct = (value: unknown) => {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}%` : "待补";
  };
  const homeMarginEtfAlignmentLabel = homeMarginEtfAlignmentStatus === "aligned_data_date"
    ? `同批同日 ${homeEtfDataDate}`
    : homeMarginEtfAlignmentStatus === "mixed_data_dates"
      ? `同一回放版本，ETF ${homeEtfDataDate} / 融资 ${homeMarginDataDate} 跨日`
      : homeMarginEtfAlignmentStatus === "etf_data_date_missing"
        ? `同一回放版本，ETF 缺数据日 / 融资 ${homeMarginDataDate}`
        : homeMarginEtfSameResultBound
          ? "同一回放版本，数据日期仍待补"
          : "ETF 与融资尚未完成同批回放";
  const ordinaryHomeMarginEtfRiskStatus = homeEtfReady || homeMarginReady
    ? `ETF ${homeEtfProviderRows.length} 行、融资事实已回放；${homeMarginEtfAlignmentLabel}。当前仍不新增融资。`
    : ordinaryHomeCandidateReadable
      ? `从下一票候选过来时，先看 ETF/融资页的现金线和候选风险；${ordinaryHomeCandidateGroupLabel} 只做研究顺序。`
      : "ETF/融资风险等待候选或确认结果；缺数据时按保守处理，不新增融资。";
  const ordinaryHomeMarginEtfPreviewRows = homeEtfProviderRows.map((row, index) => ({
    序号: index + 1,
    ETF: `${homeText(row.name, "ETF")} (${homeText(row.code, "代码待补")})`,
    数据日: homeText(row.trade_date, homeEtfDataDate),
    收盘: homeText(row.close, "待补"),
    涨跌幅: homePct(row.pct_chg),
    成交额: homeYi(row.amount_yi ?? row.turnover_yi),
    来源: homeText(row.source, "本地 ETF 快照"),
    边界: "行情只供研究复核，不生成买入、加仓或融资指令"
  }));
  const ordinaryHomeMarginEtfRiskItems: MetricItem[] = [
    {
      label: "同批状态",
      value: homeMarginEtfAlignmentLabel,
      tone: homeMarginEtfAlignmentStatus === "aligned_data_date" ? "good" : "warn"
    },
    {
      label: "ETF 行情",
      value: homeEtfReady
        ? `${homeEtfProviderRows.length} 只 / ${homeEtfDataDate}；成交额 ${homeEtfProviderRows.map((row) => homeYi(row.amount_yi ?? row.turnover_yi)).join(" / ")}`
        : "ETF 行情待补；去 ETF/融资页手动补数",
      tone: homeEtfReady ? "good" : "warn"
    },
    {
      label: "融资事实",
      value: homeMarginReady
        ? `${homeMarginDataDate}；融资余额 ${homeYi(homeMarginPacket.financing_balance_yi)} / 当日融资买入额 ${homeYi(homeMarginPacket.financing_buy_amount_yi ?? homeMarginPacket.financing_buy_yi)} / 两融余额 ${homeYi(homeMarginPacket.margin_balance_yi)}`
        : "融资事实待补；缺失时不推断杠杆改善",
      tone: homeMarginReady ? "good" : "warn"
    },
    {
      label: "风险结论",
      value: "不新增融资；ETF 候选与行情不是买入、加仓或加融资指令",
      tone: "good"
    },
    {
      label: "现在点哪里",
      value: "打开 ETF/融资风险页；必要时回候选池复核下一票",
      tone: "good"
    }
  ];
  const dailyCommandP4OrdinaryFirstItems: MetricItem[] = [
    { label: "默认视图", value: "P0 联通、P1 确认、P2 三面、P3 结果先显示", tone: "good" },
    { label: "工程审计", value: "默认折叠在 P4-P6 补证 / 审计路径和开发详情", tone: "good" },
    { label: "普通下一步", value: dailyCommandPrimaryActionLabel, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "P5", value: "DeepSeek governed executor 单独补，不阻塞 Tushare-first 和基础图谱", tone: "good" },
    { label: "P6", value: "14 LTG strict closeout 只作为回归门，不混入普通投研路径", tone: "warn" },
    { label: "边界", value: "普通优先模式不展示 raw packet、raw log、敏感凭据、provider error 或未脱敏模型输出", tone: "good" }
  ];
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
    `次日图谱：${dailyCommandNextSessionReadableStatus}`,
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
          当前状态: dailyCommandNextSessionReadableStatus,
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
      当前状态: modelStrategyP5StatusLabel,
      用户下一步: modelStrategyP5NextAllowedAction,
      证据: "GET /api/model-strategy/cache governed_executor",
      边界: dailyCommandDeepSeekGovernanceBoundary
    }
  ];
  const dailyCommandP2P3ConnectionReady = dailyCommandP2ThreeSurfaceReady && dailyCommandP3OneGlanceReadable;
  const dailyCommandP2P3ConnectionSentence = dailyCommandP2P3ConnectionReady
    ? `${dailyCommandConfirmedSymbolLabel} P2/P3 已接通：P2 cache / call_ledger / packet 三面和 P3 可读结果都能从首页同一条确认链回放。`
    : `${dailyCommandConfirmedSymbolLabel} P2/P3 等待接通：${dailyCommandP2ThreeSurfaceReady ? "P2 三面已回放" : `P2 还缺 ${dailyCommandP2MissingSurfaceLabel}`}；${dailyCommandP3OneGlanceReadable ? "P3 可读结果已回放" : "P3 可读结果待回放"}。`;
  const dailyCommandP2P3ConnectionPrimaryHref = dailyCommandP2P3ConnectionReady
    ? "#factor"
    : dailyCommandLatestTaskId
      ? "#tasks"
      : dailyCommandCandidateConfirmHref;
  const dailyCommandP2P3ConnectionPrimaryLabel = dailyCommandP2P3ConnectionReady
    ? "去股票量化推演复核"
    : dailyCommandLatestTaskId
      ? "看最近确认进度"
      : "确认一只股票";
  const dailyCommandP2P3ConnectionActionBoundary =
    "P2/P3 接通入口只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek、不交易";
  const dailyCommandP2P3ConnectionItems: MetricItem[] = [
    {
      label: "P2 三面",
      value: dailyCommandP2ThreeSurfaceReady ? dailyCommandP2SurfaceCompletionLabel : `缺口：${dailyCommandP2MissingSurfaceLabel}`,
      tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "P3 结果",
      value: dailyCommandP3OneGlanceReadable ? dailyCommandExplainableResultLabel : "等待可读结论",
      tone: dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "同源确认",
      value: dailyCommandP3OneGlanceSourceTask || dailyCommandLatestTaskId || "等待确认 task",
      tone: dailyCommandP3OneGlanceSourceTask && dailyCommandP3OneGlanceSourceTask !== "等待确认回执" ? "good" : dailyCommandLatestTaskId ? "good" : "warn"
    },
    {
      label: "下一步",
      value: dailyCommandP2P3ConnectionReady
        ? "打开股票量化推演和次日图谱复核；不要把结果当买入指令"
        : dailyCommandP2ThreeSurfaceReady
          ? "等待 P3 可读结果回放；不要从首页重复启动确认链"
          : "先看最近确认进度；任务完成后刷新本地三面回放",
      tone: dailyCommandP2P3ConnectionReady ? "good" : "warn"
    },
    {
      label: "主入口",
      value: dailyCommandP2P3ConnectionPrimaryLabel,
      tone: dailyCommandP2P3ConnectionReady ? "good" : dailyCommandLatestTaskId ? "warn" : "neutral"
    },
    {
      label: "边界",
      value: dailyCommandP2P3ConnectionActionBoundary,
      tone: "good"
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
    { label: "恢复闸门表达式", value: dailyCommandStartupRecoveryGateExpression, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
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
    { label: "次日图谱", value: dailyCommandNextSessionReadableStatus, tone: dailyCommandNextSessionTone },
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
    setHomeQuantReadbackRefreshing(true);
    const readbackJobs = [
      getCandidateRadarCache().then((res) => {
        setCandidates(res.data);
        if (res.ok === false) setError((current) => current || `candidate: ${res.error ?? "request_not_ok"}`);
      }).catch((err) => {
        setError((current) => current || `candidate: ${err instanceof Error ? err.message : String(err)}`);
      }),
      getFactorQuantCache().then((res) => setFactor(res.data)).catch(() => undefined),
      getNextSessionCache().then((res) => setNext(res.data)).catch(() => undefined),
      getPacket("command_center_etf_packet").then((res) => setHomeEtfPacket(res.data)).catch(() => undefined),
      getPacket("command_center_margin_packet").then((res) => setHomeMarginPacket(res.data)).catch(() => undefined),
      getPacket("command_center_margin_etf_refresh_receipt").then((res) => setHomeMarginEtfReceipt(res.data)).catch(() => undefined),
      getTasks().then((res) => {
        setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
        setTaskIndex(res.data);
        setTasks(res.data.tasks ?? []);
      }).catch(() => undefined),
    ];
    void Promise.allSettled(readbackJobs).then(() => {
      setHomeQuantReadbackLastRefresh(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    }).finally(() => {
      setHomeQuantReadbackRefreshing(false);
    });
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
        setHomeQuantSymbolTouched(false);
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
    <div className="route-cache-loading-shell" data-route-cache-loading={loading ? "true" : "false"} data-route-cache-ready={initialLayoutReady ? "true" : "false"} data-route-cache-degraded={Boolean(error) ? "true" : "false"} aria-busy={loading} data-ltg10-component-id="CommandCenterHome">
      <RouteCacheLoadingOverlay loading={loading} />
      <div className="page-head">
        <div>
          <h1 data-ltg10-route-heading="home">今日作战台</h1>
          <p>先看能不能用、当前标的、最近结果和下一步。</p>
        </div>
        <StatusBadge label={dailyCommandStatusLabel} tone={dailyCommandHealthOk ? "good" : "warn"} />
      </div>
      <PacketCard title="今日可用" subtitle="普通首页只看能不能用、看哪只票、有没有结果、下一步点哪里" status={ordinaryHomeStatusBadge}>
        <div className="home-primary-status-stability-frame">
          <div className="home-status-metrics-stability-slot">
            <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeStatusItems)} />
          </div>
          <div className="home-market-freshness-stability-slot" aria-label="ordinary home market session freshness">
            <h3>市场会话与数据新鲜度</h3>
            <p className="ordinary-status-note" aria-live="polite">{ordinaryHomeFreshnessExplanation}</p>
            <MetricGrid items={ordinaryHomeMarketSessionItems} />
            {ordinaryHomeFreshnessNeedsAttention ? (
              <div className="actions" aria-label="ordinary home market session freshness actions">
                <a href="#dataHealth" title="查看数据健康；只读本地缓存，不刷新外部数据源" aria-label="open data health from home market session freshness">查看数据健康</a>
              </div>
            ) : null}
          </div>
        </div>
        <p className="ordinary-status-note" aria-label="ordinary home input confirm first sentence">输入确认速读：输入只做本地校验；确认后看最近结果、候选池、ETF/融资、股票量化推演和次日图谱。</p>
        <div id="home-p1-symbol-confirm" className="actions" aria-label="daily command ordinary home primary controls">
          <input
            value={homeQuantSymbol}
            onChange={(event) => {
              setHomeQuantSymbolTouched(true);
              setHomeQuantSymbol(event.target.value);
              setHomeQuantSubmitError("");
            }}
            placeholder="002008.SZ 或 002008"
            aria-label="ordinary home stock symbol"
            title="输入只做本地校验"
          />
          {ordinaryHomePrimaryActionKind === "link" ? (
            <a href={ordinaryHomeNextHref} title={ordinaryHomePrimaryActionTitle} aria-label="open ordinary home next action">{ordinaryHomePrimaryActionText}</a>
          ) : (
            <button
              disabled={ordinaryHomePrimaryActionDisabled}
              onClick={ordinaryHomePrimaryActionKind === "refresh" ? refreshHomeResearchReadback : launchHomeQuantProjection}
              title={ordinaryHomePrimaryActionTitle}
              aria-label="run ordinary home next action"
            >{ordinaryHomePrimaryActionText}</button>
          )}
        </div>
        {homeQuantSubmitError ? <p className="ordinary-status-note" aria-live="polite">确认失败：请检查本地连接后重试。</p> : null}
        <p className="ordinary-status-note home-confirm-status-line" aria-label="ordinary home confirm status" aria-live="polite">{ordinaryHomeConfirmStatusLine}</p>
        <div className="actions" aria-label="ordinary home visible result quick actions">
          <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor result from visible home quick actions">股票量化推演</a>
          <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next result from visible home quick actions">次日图谱</a>
          <a href="#storage" title="切换到存储层 current/last-good；只读本地回放，不启动后台流程" aria-label="open storage current result from visible home quick actions">current/last-good</a>
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from visible home quick actions">换一只票</a>
        </div>
        <details
          className="developer-audit-details"
          aria-label="ordinary home supporting research details"
          onToggle={(event) => {
            if (event.currentTarget.open) setAuditReadbackRequested(true);
          }}
        >
          <summary>研究辅助 / 审计详情</summary>
          <p className="risk-note">候选、数据回放、任务进度、路线 QA 和来源细节统一收在这里；普通使用只需看上方四项和下一步按钮。</p>
        <div aria-label="ordinary home app visible now summary">
          <h3>打开 app 能看到什么</h3>
          <p className="ordinary-status-note" aria-label="ordinary home app visible now sentence" aria-live="polite">{ordinaryHomeAppVisibleNowSentence}</p>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeAppVisibleNowItems)} />
          <div className="actions" aria-label="ordinary home app visible now local actions">
            <a href={dailyCommandHomeConfirmHref} title="跳到首页确认股票代码；输入保持静默" aria-label="open home confirm from visible now summary">确认股票</a>
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate radar from home visible now summary">下一票雷达</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核 Tushare 数据凭证、权限、空窗口和本地结果包缺口" aria-label="open data capability from home visible now summary">数据能力</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from home visible now summary">ETF/融资风险</a>
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from home visible now summary">股票量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next session from home visible now summary">次日图谱</a>
            <a href="#storage" title="切换到存储层 current/last-good；只读本地回放，不创建 task" aria-label="open storage current result from home visible now summary">current/last-good</a>
          </div>
          <p className="risk-note">这个条带只回答普通用户打开首页能看到什么：本地是否接上、当前标的、最近结果、来源层、缺口和下一步入口；普通链接只切换本地页面或锚点，不启动确认流程、不调用外部服务、不交易、不改策略。</p>
        </div>
        <div aria-label="ordinary home first screen recent result read">
          <h3>最近结果速读</h3>
          <p className="ordinary-status-note" aria-label="ordinary home recent result summary" aria-live="polite">{ordinaryHomeRecentResultSummary}</p>
          <div aria-label="ordinary home plain result conclusion">
            <h3>普通结论</h3>
            <p className="ordinary-status-note" aria-label="ordinary home plain result conclusion text" aria-live="polite">{ordinaryHomePlainConclusionText}</p>
            <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomePlainConclusionItems)} />
          </div>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeRecentResultItems)} />
          <div className="actions" aria-label="ordinary home recent result local readback actions">
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor result from ordinary home recent result">股票量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next result from ordinary home recent result">次日图谱</a>
            <a href="#storage" title="切换到存储层 current/last-good；只读本地回放，不创建 task" aria-label="open storage current result from ordinary home recent result">current/last-good</a>
          </div>
          <p className="risk-note">这张速读只读首页已拿到的本地记录、数据凭证、结果包和任务索引；没有结果时显示等待或待补，不把空结果当无风险，也不会重复创建确认任务。</p>
        </div>
        <div aria-label="ordinary home first screen tushare data card">
          <h3>确认后数据回放</h3>
          <p className="ordinary-status-note" aria-label="ordinary home first screen tushare data card summary" aria-live="polite">{dailyCommandTushareDataCardSummary}</p>
          <MetricGrid items={ordinaryHomeMetricItems(dailyCommandTushareDataCardItems)} />
          <p className="ordinary-status-note" aria-label="ordinary home first screen tushare degraded review" aria-live="polite">{dailyCommandTushareDataCardReviewSentence}</p>
          <div className="actions" aria-label="ordinary home first screen tushare data card actions">
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from ordinary home tushare data card">确认或换一只票</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核数据凭证、权限、空窗口和降级说明" aria-label="open data capability from ordinary home tushare data card">数据能力</a>
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from ordinary home tushare data card">股票量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next from ordinary home tushare data card">次日图谱</a>
          </div>
          <p className="risk-note">这张数据回放只读确认后的本地记录、数据调用记录和结果摘要；没有回放时显示等待或待补，不从首页补调外部数据、不重复发起确认流程、不交易、不改策略。</p>
        </div>
        <div aria-label="ordinary home first screen research route map">
          <h3>今日投研路径</h3>
          <p className="ordinary-status-note">打开 app 先按这条路走：确认股票、看候选、查 ETF/融资风险、再看次日图谱；缺数据时显示 pending/degraded，不把空结果当无风险。</p>
          <MetricGrid items={ordinaryHomeMetricItems(dailyCommandResearchRouteMapItems)} />
          <div className="actions" aria-label="ordinary home research route map actions">
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from ordinary home route map">确认股票</a>
            <a href="#candidates/candidate-pool" title="切换到下一票候选池；只读本地候选缓存" aria-label="open candidate pool from ordinary home route map">候选池</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from ordinary home route map">ETF/融资风险</a>
            <a href="#next/next-session-chart" title="切换到次日图谱；只读本地图谱" aria-label="open next session from ordinary home route map">次日图谱</a>
          </div>
        </div>
        <div aria-label="ordinary home user route qa quick read">
          <h3>普通路线 QA 速读</h3>
          <p className="ordinary-status-note" aria-label="ordinary home user route qa summary" aria-live="polite">{ordinaryHomeUserRouteQaSummary}</p>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeUserRouteQaItems)} />
          <div className="actions" aria-label="ordinary home user route qa local actions">
            <a href="#audit" title="切换到调用审计；只读本地 QA 摘要和调用记录" aria-label="open audit from ordinary home user route qa">调用审计</a>
            <a href="#candidates" title="切换到下一票雷达；只读本地候选缓存" aria-label="open candidates from ordinary home user route qa">下一票雷达</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from ordinary home user route qa">ETF/融资</a>
            <a href="#factor/factor-score" title="切换到股票量化推演；只读本地结果" aria-label="open factor from ordinary home user route qa">股票量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱；只读本地图谱" aria-label="open next from ordinary home user route qa">次日图谱</a>
          </div>
          <details className="developer-audit-details" aria-label="ordinary home user route qa rows">
            <summary>查看路线 QA 覆盖</summary>
            <p className="risk-note">路线 QA 行只读 `.stock_ming_3/user_route_qa` ignored 本地报告摘要；首页不会打开浏览器、不会写截图、不会创建任务。</p>
            <DataLineageTable rows={ordinaryHomeUserRouteQaRows} />
          </details>
          <p className="risk-note">这张速读只说明普通路线是否有本地视觉和输入静默证据；它不是外部数据或模型验收、不是远端发布检查，也不是最终完成声明。</p>
        </div>
        <div aria-label="ordinary home candidate radar visible slice">
          <h3>下一票雷达速读</h3>
          <p className="ordinary-status-note" aria-label="ordinary home candidate radar readable sentence" aria-live="polite">{ordinaryHomeCandidateReadableSentence}</p>
            <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeCandidateRadarItems)} />
          <div className="actions" aria-label="ordinary home candidate radar visible actions">
            <a href={ordinaryHomeCandidatePrimaryHref} title="按当前候选状态切换到最该看的本地入口；不会创建新任务" aria-label="open primary candidate radar action from ordinary home">{ordinaryHomeCandidatePrimaryLabel}</a>
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from ordinary home radar slice">确认股票</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from ordinary home radar slice">ETF/融资风险</a>
            <a href="#next/next-session-chart" title="切换到次日图谱；只读本地图谱" aria-label="open next session from ordinary home radar slice">次日图谱</a>
          </div>
          <details className="developer-audit-details" aria-label="ordinary home candidate radar preview rows">
            <summary>查看候选预览</summary>
            <p className="risk-note">候选预览只读 CandidateRadar cache 的 Top / Watch / Excluded 或候选行；默认收起，避免首页变成雷达明细表。</p>
            <DataLineageTable rows={ordinaryHomeCandidatePreviewRows} />
          </details>
          <p className="risk-note">这张速读只读下一票雷达本地缓存；页面打开和搜索输入不创建任务、不调用外部数据或模型服务、不交易、不改写策略。</p>
        </div>
        <div aria-label="ordinary home margin etf risk bridge">
          <h3>ETF/融资风险速读</h3>
          <p className="ordinary-status-note" aria-label="ordinary home margin etf risk sentence" aria-live="polite">{ordinaryHomeMarginEtfRiskStatus}</p>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeMarginEtfRiskItems)} />
          {ordinaryHomeMarginEtfPreviewRows.length ? (
            <details className="developer-audit-details" aria-label="ordinary home etf market preview">
              <summary>查看 3 只 ETF 本地行情</summary>
              <p className="risk-note">只读已写入的 ETF 快照；表格默认收起，不在首页展示任务编号、账本或内部版本。</p>
              <DataLineageTable rows={ordinaryHomeMarginEtfPreviewRows} />
            </details>
          ) : null}
          <div className="actions" aria-label="ordinary home margin etf risk actions">
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf risk card from ordinary home">看 ETF/融资风险</a>
            <a href="#candidates/candidate-pool" title="切换到下一票候选池；只读本地候选缓存" aria-label="open candidate pool from ordinary home margin etf bridge">回候选池</a>
            <a href="#risk" title="切换到风险护栏；只读本地风险摘要" aria-label="open risk guardrails from ordinary home margin etf bridge">风险护栏</a>
          </div>
          <p className="risk-note">这张风险卡只切换本地页面；不刷新外部数据、不创建任务、不交易、不加融资、不改策略。</p>
        </div>
        <div aria-label="ordinary home first screen post confirm status">
          <h3>确认后状态</h3>
          <p className="ordinary-status-note" aria-label="ordinary home post confirm status summary" aria-live="polite">{homeQuantPostConfirmReadableSentence}</p>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomePostConfirmItems)} />
          <div aria-label="ordinary home confirm result chain">
            <h3>确认后结果链路</h3>
            <p className="ordinary-status-note" aria-label="ordinary home confirm result chain summary" aria-live="polite">{ordinaryHomeConfirmResultChainSentence}</p>
            <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeConfirmResultChainItems)} />
            <div className="actions" aria-label="ordinary home confirm result chain actions">
              <a href={ordinaryHomeProgressHref} title="切换到进度目录；只读查看本地进度" aria-label="open progress from ordinary home confirm result chain">看进度</a>
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from ordinary home confirm result chain">股票量化推演</a>
              <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next session from ordinary home confirm result chain">次日图谱</a>
            </div>
            <p className="risk-note">这里顺序只读当前确认、本地进度、本地记录和结果入口；普通链接只切换页面，不调用外部服务、不读取敏感凭据、不交易、不改策略。</p>
          </div>
          <div aria-label="ordinary home post confirm replay state strip">
            <h3>确认后回放速读</h3>
            <p className="ordinary-status-note" aria-label="ordinary home post confirm replay summary" aria-live="polite">{ordinaryHomePostConfirmReplaySummary}</p>
            <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomePostConfirmReplayItems)} />
            <p className="ordinary-status-note" aria-label="ordinary home post confirm replay action note" aria-live="polite">{ordinaryHomePostConfirmReplayActionNote}</p>
            <div className="actions" aria-label="ordinary home post confirm replay actions">
              <a href={ordinaryHomePostConfirmReplayPrimaryHref} title="按当前回放状态切换到最该看的本地入口；不会创建新任务" aria-label="open primary post confirm replay action">{ordinaryHomePostConfirmReplayPrimaryLabel}</a>
              <a href={ordinaryHomeProgressHref} title="切换到任务目录；只读查看本地任务进度" aria-label="open progress from post confirm replay">任务进度</a>
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from post confirm replay">股票量化推演</a>
              <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next session from post confirm replay">次日图谱</a>
            </div>
          </div>
          <p className="risk-note">这里先显示确认回执、任务进度、本地回放和下一步；它只读本地任务和缓存，不会重复点击确认、不调用外部数据或模型、不读取密钥、不交易或改写策略。</p>
        </div>
        <div aria-label="ordinary home first screen result route">
          <h3>确认后去哪看</h3>
          <p className="ordinary-status-note" aria-label="ordinary home result route summary" aria-live="polite">{ordinaryHomeResultRouteSummary}</p>
          <MetricGrid items={ordinaryHomeMetricItems(ordinaryHomeResultRouteItems)} />
          <div className="actions" aria-label="ordinary home first screen result route actions">
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from ordinary home result route">股票量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读本地图谱" aria-label="open next session from ordinary home result route">次日图谱</a>
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="open candidate radar from ordinary home result route">下一票雷达详情</a>
          </div>
          <p className="risk-note">这些结果入口只切换本地模块；不会新建任务、不会调用外部数据或模型服务、不会读取密钥、不会交易或改写策略。</p>
        </div>
        </details>
      </PacketCard>
      <details
        className="developer-audit-details"
        aria-label="daily command research assist audit details"
        onToggle={(event) => {
          if (event.currentTarget.open) setAuditReadbackRequested(true);
        }}
      >
        <summary>研究辅助 / 审计详情</summary>
        {/* Regression guard: 先看下一步、数据来源、缺少证据和仅供研究边界。 */}
        <p className="risk-note">这里保留任务编号、数据凭证、结果包、边界说明和模型治理状态；普通使用先看上方“今日可用”。</p>
        <p className="risk-note">{ordinaryHomeRecoveryAuditNote}</p>
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
            { label: "首页读法", value: "先看本地联通，再确认股票代码；确认后看任务进度、量化推演和次日图谱", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
            { label: "边用边看", value: dailyCommandFastApiProgressWatchLabel, tone: dailyCommandLatestTaskId || dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "投研入口", value: dailyCommandNeedsStartupRecovery ? "先看一键启动预检" : "在首页确认股票代码；需要详情再进下一票雷达", tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
            { label: "安全边界", value: "打开页面和输入代码不外联；确认按钮才触发 Tushare-first", tone: "good" }
          ]}
        />
        <div aria-label="daily command usable now one glance">
          <h3>今日可用状态</h3>
          <MetricGrid items={dailyCommandUsableNowOneGlanceItems} />
          <p className="risk-note">打开软件后先看这六格：本地能不能用、当前标的、最近任务、P2/P3、下一步和安全边界；它只读本地回放，不创建 task。</p>
        </div>
        <div aria-label="daily command local fastapi open proof">
          <h3>打开后接线证明</h3>
          <MetricGrid items={dailyCommandOpenFastApiProofItems} />
          <p className="risk-note">这条证明只合成当前页面已拿到的 health、bootstrap、desktop preflight 和 React 状态；它不启动 FastAPI/Vite、不创建 task、不调用 Tushare/DeepSeek/GitHub，也不读取或展示 token/key 或敏感凭据。</p>
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
              { label: "候选地址", value: API_BASE_CANDIDATE_DISPLAY_URLS.join(" / "), tone: "good" },
              { label: "接口读法", value: "多接口本地聚合：health / bootstrap / preflight / radar / factor / next / tasks", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" }
            ]}
          />
          <p className="risk-note">接线地址来自前端本机 FastAPI 自动接线记录；候选地址只展示本机 127.0.0.1/localhost fallback。该卡只读 FastAPI health、bootstrap status 和 desktop preflight cache；不会启动服务、不会创建任务、不会调用 Tushare/DeepSeek/GitHub，也不会暴露敏感凭据。</p>
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
          <p className="ordinary-status-note" aria-label="daily command p1 visible progress sentence" aria-live="polite">{dailyCommandP1VisibleProgressSentence}</p>
          <p className="ordinary-status-note" aria-label="daily command p2 visible writeback sentence" aria-live="polite">{dailyCommandP2VisibleWritebackSentence}</p>
          <p className="ordinary-status-note" aria-label="daily command p3 visible explainable sentence" aria-live="polite">{dailyCommandP3VisibleExplainableSentence}</p>
          <p className="ordinary-status-note" aria-label="daily command p5 visible governance sentence" aria-live="polite">{dailyCommandP5VisibleGovernanceSentence}</p>
          <p className="ordinary-status-note" aria-label="daily command current research snapshot readable sentence" aria-live="polite">{dailyCommandCurrentResearchSnapshotReadableSentence}</p>
          <MetricGrid items={dailyCommandCurrentResearchSnapshotItems} />
          <p className="risk-note">这张首屏快照只读最近确认任务、Tushare-first 数据链、P2 三面、P3 可读结论和次日图谱回放；P5 governed 状态只作非阻塞摘要；不会重复创建任务、不补调 Tushare/DeepSeek、不展示敏感凭据，也不交易或修改 strategy action。</p>
        </div>
        <DataLineageTable rows={dailyCommandUsableShortestPathPrimaryRows} />
        <div className="actions" aria-label="daily command usable path front actions">
          <a href={dailyCommandPrimaryActionHref} title={dailyCommandPrimaryActionBoundary} aria-label="open usable path primary action">{dailyCommandPrimaryActionLabel}</a>
          <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读回放本地 P2/P3 结果" aria-label="open stock quant from usable path progress">股票量化推演</a>
          <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读回放本地图谱数据" aria-label="open next session from usable path progress">次日图谱</a>
        </div>
        <p className="risk-note">这张进度卡只读首页已回放的 health、CandidateRadar cache、任务索引和本地结果；不会创建任务、不会调用 Tushare/DeepSeek/GitHub、不会读取敏感凭据、不会交易或修改 strategy action；敏感凭据仍不展示。</p>
      </PacketCard>
      <PacketCard title="P0 现在能不能用" subtitle="普通用户打开软件后的 10 秒判断" status={dailyCommandP0LocalReadinessReady ? "ready" : "check"}>
        <MetricGrid
          items={[
            {
              label: "结论",
              value: dailyCommandP0LocalReadinessReady
                ? "可以用：本地四段已接上"
                : dailyCommandHealthOk
                  ? "本地已接上：确认闸门等待 P0 证据"
                  : "先恢复：本地四段还没全部 ready",
              tone: dailyCommandHealthOk ? "good" : "warn"
            },
            { label: "现在点哪里", value: ordinaryHomeP0ActionLabel, tone: dailyCommandHealthOk ? "good" : "warn" },
            { label: "失败看哪里", value: "桌面壳预检里的 FastAPI / bootstrap / preflight / React 分段诊断", tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
            {
              label: "进入 P1 条件",
              value: dailyCommandP0LocalReadinessReady
                ? "health、bootstrap、desktop preflight、React 四段 ready，可以确认股票代码"
                : dailyCommandHealthOk
                  ? "本地只读入口已接上；确认按钮等待 bootstrap / preflight / P0 connection evidence"
                  : "health、bootstrap、desktop preflight、React 四段 ready 后再确认股票代码",
              tone: dailyCommandHealthOk ? "good" : "warn"
            },
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
        <div aria-label="daily command home p1 symbol confirmation">
          <MetricGrid items={homeQuantConfirmItems} />
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
              title={homeQuantSubmitActionHint}
              aria-label={homeQuantSubmitActionHint}
            >{homeQuantSubmitting ? "提交中..." : "确认股票并启动数据链"}</button>
            <button
              disabled={homeQuantReadbackRefreshing}
              onClick={refreshHomeResearchReadback}
              title={homeQuantManualReadbackBoundary}
              aria-label="refresh home local research readback only"
            >{homeQuantManualReadbackButtonLabel}</button>
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达详情页；同一条 P1 确认链路" aria-label="open candidate radar detail from home p1 confirm">下一票雷达详情</a>
          </div>
          <p className="ordinary-status-note" aria-label="daily command home p1 confirm action hint" aria-live="polite">{homeQuantSubmitActionHint}</p>
          <p className="ordinary-status-note" aria-label="daily command home manual readback boundary">{homeQuantManualReadbackBoundary}</p>
          <p className="ordinary-status-note" aria-label="daily command home p1 server contract line">{homeQuantP1ServerContractLine}</p>
          <details className="developer-audit-details" aria-label="daily command home p1 confirm button chain proof">
            <summary>查看确认链路证明</summary>
            <h3>确认按钮链路证明</h3>
            <p className="risk-note">点击前先看这五步：输入静默、P0 gate、确认按钮创建 task、任务进度、本地三面回放；需要排查时再看这五步：输入静默、P0 gate、确认按钮创建 task、任务进度、本地三面回放；本表只解释链路，不创建 task。</p>
            <p className="risk-note">浏览器网络证据：{homeP1BrowserEvidenceLabel}；它不阻塞手动确认使用，也不作为生产验收完成声明。</p>
            <DataLineageTable rows={homeQuantConfirmButtonChainRows} />
          </details>
          <p className="risk-note" aria-label="daily command home p1 symbol autofill boundary">当前标的自动填入只来自 CandidateRadar cache / GET /api/tasks；不会自动点击确认、不创建 task、不调用 Tushare/DeepSeek，手动修改后不再覆盖输入。</p>
          <p className="ordinary-status-note" aria-label="daily command home post confirm readback state" aria-live="polite">{homeQuantPostConfirmReadbackState}</p>
          <div aria-label="daily command home p1 immediate receipt">
            <p className="ordinary-status-note" aria-label="daily command home p1 immediate receipt sentence" aria-live="polite">{homeQuantImmediateReceiptSentence}</p>
            <MetricGrid items={homeQuantImmediateReceiptItems} />
          </div>
          <div aria-label="daily command home post confirm handoff">
            <h3>确认后看板</h3>
            <p className="risk-note">确认后下一步常驻在这里：没有回执时先看点击后会出现什么；任务编号出现或从本地 cache 恢复后，先看任务进度；成功后按股票量化推演和次日图谱回放。这里的链接只切换本地页面，不重复启动确认链。</p>
            <p className="ordinary-status-note" aria-label="daily command home post confirm readable result" aria-live="polite">{homeQuantPostConfirmReadableSentence}</p>
            <div aria-label="daily command home result route strip">
              <h3>确认后结果路标</h3>
              <p className="ordinary-status-note" aria-label="daily command home result route sentence" aria-live="polite">{homeQuantResultRouteSentence}</p>
              <MetricGrid items={homeQuantResultRouteItems} />
              <div className="actions" aria-label="daily command home result route actions">
                <a href="#factor/factor-score" title="股票量化推演入口：切换到支持/压制摘要；只读回放本地结果" aria-label="open factor support suppress from home result route">股票量化推演</a>
                <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读回放本地图谱" aria-label="open next chart from home result route">次日图谱</a>
                <a href={dailyCommandCandidateConfirmHref} title="切换到确认输入区；换标的仍需确认按钮" aria-label="open confirm input from home result route">换一只票</a>
              </div>
              <p className="risk-note">{homeQuantResultRouteBoundary}</p>
            </div>
            {homeQuantVisibleTaskId ? (
              <>
                <div aria-label="daily command home p1 p2 p3 checkpoint">
                  <h3>P1/P2/P3 一眼 checkpoint</h3>
                  <MetricGrid items={homeQuantP1P2P3CheckpointItems} />
                  <p className="risk-note">这条 checkpoint 只合成现有确认回执、Tushare 数据回放、P2 三面、P3 可读结论和量化推演入口；这条 checkpoint 只合成现有 task id、Tushare ledger、P2 三面、P3 可读结论和 Factor handoff；不创建 task、不补调 provider/model、不展示 raw packet；不重复启动确认链、不补调数据源或模型、不展示原始包。</p>
                </div>
              </>
            ) : null}
            <div aria-label="daily command home post confirm one glance">
              <MetricGrid items={homeQuantPostConfirmOneGlanceItems} />
            </div>
            <div aria-label="daily command home post confirm p2 three surfaces">
              <h3>P2 三面写回</h3>
              <MetricGrid items={dailyCommandP2ThreeSurfaceProofItems} />
              <p className="risk-note">确认后先看这三面：cache 能刷新回放、call_ledger 来自确认任务、packet 是本地结果包；本区只读已有三面，不创建第二个 task、不补调 Tushare/DeepSeek。</p>
            </div>
            <div aria-label="daily command home post confirm p3 explainable result">
              <h3>P3 可解释结果</h3>
              <p className="ordinary-status-note" aria-live="polite">{dailyCommandP3VisibleExplainableSentence}</p>
              <MetricGrid items={dailyCommandP3ExplainableProofItems} />
              <p className="risk-note">确认后再看这组解释：结论、来源、缺口、模型状态和结果入口都来自本地 cache / ledger / packet；这里只读回放，不创建 task、不调用 DeepSeek、不生成买卖动作；不会创建 task、不会调用 DeepSeek、不会交易或修改 strategy action。</p>
            </div>
            <DataLineageTable rows={homeQuantPostConfirmHandoffRows} />
            <div className="actions" aria-label="daily command home post confirm handoff actions">
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress after home symbol confirm">查看任务进度</a>
              <a href="#factor" title="切换到股票量化推演；只读回放确认后的本地结果" aria-label="open factor after home symbol confirm">股票量化推演</a>
              <a href="#next" title="切换到次日图谱；只读回放确认后的本地图谱" aria-label="open next session after home symbol confirm">次日图谱</a>
              <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="open candidate radar confirm input after home symbol confirm">下一票雷达确认输入区</a>
            </div>
            <p className="risk-note">确认前看板只是预览；确认后只回放本地确认结果和数据写入状态。它不自动点击确认、不调用 Tushare/DeepSeek、不下单、不改交易策略。</p>
          </div>
          {homeQuantSubmitError ? (
            <div aria-label="daily command home p1 submit failure recovery">
              <p className="risk-note" aria-live="polite">首页确认任务创建失败：{homeQuantSubmitError}</p>
              <DataLineageTable rows={homeQuantSubmitFailureRecoveryRows} />
            </div>
          ) : null}
          {homeQuantVisibleTaskCanPoll ? <TaskStatusPanel taskId={homeQuantVisibleTaskId} onSuccess={refreshHomeResearchReadback} /> : null}
          {homeQuantVisibleTaskId && !homeQuantVisibleTaskCanPoll ? (
            <p className="risk-note" aria-label="daily command home recovered task cache-only notice">最近确认 task 来自 CandidateRadar cache 只读回放；最近任务来自 CandidateRadar cache 只读回放，不启动 TaskStatusPanel 轮询；当前任务目录没有可轮询记录，首页不会启动 TaskStatusPanel，也不会创建第二个 task。</p>
          ) : null}
          {homeQuantReceipt ? (
            <details className="developer-audit-details" aria-label="daily command home p1 receipt audit details">
              <summary>任务回执 / 审计详情</summary>
              <p className="risk-note">完整 POST task receipt 默认下沉；普通路径先看上方任务进度、量化推演和次日图谱。</p>
              <TaskLaunchReceipt receipt={homeQuantReceipt} />
            </details>
          ) : null}
          <details className="developer-audit-details" aria-label="daily command home p1 technical boundary details">
            <summary>确认按钮技术边界</summary>
            <p className="risk-note">首页确认按钮复用 POST /api/candidate-radar/quant-projection：P0 gate 通过后才启用；成功后只从 CandidateRadar cache / call_ledger / packet 回放 P2/P3。P1 手动确认链路已接入本地 runtime；浏览器网络证据和自动提交仍单独补，不当作生产验收。页面打开、输入、React render 和 GET cache 不外联，不调用 DeepSeek，不交易、不改交易策略。</p>
          </details>
        </div>
      </PacketCard>
      <PacketCard title="P1 Tushare-first 链路速读" subtitle="确认按钮、数据回放、DeepSeek 单独治理和安全边界" status={dailyCommandTushareFirstLedgerReady ? "ledger_ready" : "waiting_confirm"}>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "P1 最短路径", value: dailyCommandP1ShortestPathLabel, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
            { label: "确认链", value: dailyCommandTushareFirstStatus, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "数据回放", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "DeepSeek", value: dailyCommandTushareFirstDeepSeekLabel, tone: "good" },
            { label: "下一步", value: dailyCommandTushareFirstLedgerReady ? "继续看 P2 三面和 P3 结论" : "先在首页或下一票雷达点击确认按钮", tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "边界", value: dailyCommandTushareFirstBoundary, tone: "good" }
          ]}
        />
        <div aria-label="daily command p1 tushare data card">
          <h3>确认后数据回放</h3>
          <p className="ordinary-status-note" aria-label="daily command p1 tushare data card summary" aria-live="polite">{dailyCommandTushareDataCardSummary}</p>
          <MetricGrid items={dailyCommandTushareDataCardItems} />
          <p className="risk-note">首页只把确认后已有的 Tushare-first 本地回放整理成数据卡；接口明细继续在下一票雷达和股票量化推演页展开，不从首页补调数据源、模型或交易。</p>
        </div>
        <div aria-label="daily command p1 shortest path checkpoint">
          <h3>P1 最短路径 checkpoint</h3>
          <MetricGrid
            items={[
              { label: "状态", value: dailyCommandP1ShortestPathStatus, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
              { label: "速读", value: dailyCommandP1ShortestPathLabel, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
              { label: "下一步", value: dailyCommandP1ShortestPathNext, tone: dailyCommandP1ShortestPathReady ? "good" : "warn" },
              { label: "边界", value: dailyCommandP1ShortestPathBoundary, tone: "good" }
            ]}
          />
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_p1_shortest_path_checkpoint：普通用户直接看确认按钮后的 Tushare-first 是否跑通、下一步去哪，不需要展开 raw packet 或工程审计。</p>
        </div>
        <details className="developer-audit-details" aria-label="daily command p1 table details demoted">
          <summary>P1 链路表格明细</summary>
          <p className="risk-note">普通路径先看上方 P1 总览、确认后看板、P2 三面和 P3 结论；P1 四步表和确认回执表只在排障或验收时展开。</p>
          <div aria-label="daily command p1 tushare first front row">
            <h3>P1 链路四步</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_tushare_first_chain_rows：普通用户只看输入是否静默、确认是否接收、Tushare 数据是否回放、DeepSeek 是否单独治理；输入是否静默、确认按钮是否创建 task、Tushare ledger 是否回放、DeepSeek 是否 skipped；工程明细继续下沉。</p>
            <DataLineageTable rows={dailyCommandTushareFirstRows} />
          </div>
          <div aria-label="daily command p1 confirm task readback proof">
            <h3>P1 确认回执</h3>
            <p className="risk-note">P1 确认任务回放；优先读取 CandidateRadar 的 search_quant_projection_confirmed_task_receipt_rows 和 search_quant_projection_task_readback_rows；只读 search_quant_projection_confirmed_task_receipt_rows / task_readback_rows；不创建第二个 task。</p>
            <MetricGrid
              items={[
                { label: "确认回执", value: candidateQuantConfirmedTaskReceiptRows.length ? `${candidateQuantConfirmedTaskReceiptRows.length} 行已回放` : "等待确认回执", tone: candidateQuantConfirmedTaskReceiptRows.length ? "good" : "warn" },
                { label: "进度状态", value: candidateQuantTaskReadbackRows.length ? `${candidateQuantTaskReadbackRows.length} 行已回放` : "等待进度状态", tone: candidateQuantTaskReadbackRows.length ? "good" : "warn" },
                { label: "来源回执", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
                { label: "回放边界", value: "只读确认回执和进度回放；不重复启动确认链", tone: "good" }
              ]}
            />
            <p className="risk-note">优先读取 CandidateRadar 的确认回执和进度回放，让点击确认后的编号、安全步骤和本地进度直接可见。</p>
            <DataLineageTable rows={dailyCommandP1ConfirmTaskReadbackRows} />
          </div>
        </details>
        <div className="actions" aria-label="daily command p1 tushare first front actions">
          <a href={dailyCommandCandidateConfirmHref} title="回到下一票雷达确认输入区；输入静默，确认按钮才创建 Tushare-first task" aria-label="open candidate confirm from p1 tushare first front row">确认或换一只票</a>
          <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核 Tushare ledger、权限、空窗口和本地 packet 缺口" aria-label="open data capability from home p1 tushare data card">数据能力</a>
          <a href="#factor" title="切换到股票量化推演；只读回放 Tushare-first 后的本地结果" aria-label="open factor after p1 tushare first front row">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放 Tushare-first 后的本地图谱" aria-label="open next session after p1 tushare first front row">次日图谱</a>
        </div>
        <p className="risk-note">P1 速读只回放已写入的 POST task / call_ledger / packet 证据；P1 速读只回放已写入的确认回执和本地结果，用来组成首页数据卡；不会从首页回放卡创建第二个 task、补调 Tushare/DeepSeek、读取 token/key、执行交易或修改 strategy action；不会从首页回放卡重复启动确认链、补调 Tushare/DeepSeek、读取敏感凭据、执行交易或修改交易策略。</p>
      </PacketCard>
      <PacketCard title="当前可用投研链路" subtitle="当前标的、P1 确认、P2 三面、P3 结论和下一步" status={dailyCommandResearchWorkflowStatus}>
        <p className="ordinary-status-note" aria-label="daily command current research workflow readable result" aria-live="polite">{dailyCommandResearchWorkflowReadableSentence}</p>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "P1 确认", value: dailyCommandLatestTaskId ? `${dailyCommandLatestTaskStatus}: ${dailyCommandLatestTaskId}` : "等待确认按钮", tone: dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "P2 三面", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "下一步", value: dailyCommandResearchWorkflowNext },
            { label: "数据能力", value: dailyCommandDataCapabilityReviewLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "P5 单独补证", value: modelStrategyP5StatusLabel, tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good" },
            { label: "P5 不阻塞", value: modelStrategyP5NextAllowedAction, tone: "good" },
            { label: "边界", value: "当前链路卡只读 CandidateRadar cache / ledger / packet；只有首页确认卡创建 P1 task；不交易；当前链路卡只读本地三面结果；只有首页确认卡启动 P1 确认；不交易", tone: "good" }
          ]}
        />
        <DataLineageTable rows={dailyCommandResearchWorkflowRows} />
        <div className="actions" aria-label="daily command current research workflow actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入代码后仍需确认按钮" aria-label="open candidate radar confirm from current research workflow">确认或换一只票</a>
          <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核当前标的的数据账本和 degraded 缺口" aria-label="open data capability from current research workflow">数据能力</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from current research workflow">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session replay from current research workflow">次日图谱</a>
        </div>
        <p className="risk-note">这张卡把 P1/P2/P3 放到首页前排：页面打开和搜索输入不外联；只有首页或下一票雷达确认按钮可以创建 Tushare-first POST task，DeepSeek governed executor 单独补。</p>
      </PacketCard>
      <PacketCard title="P2/P3 接通 checkpoint" subtitle="首页直接判断三面写回和可读结果是否连成同一条本地确认链" status={dailyCommandP2P3ConnectionReady ? "p2_p3_connected" : "waiting_replay"}>
        <p className="ordinary-status-note" aria-label="daily command p2 p3 connection sentence" aria-live="polite">{dailyCommandP2P3ConnectionSentence}</p>
        <MetricGrid items={dailyCommandP2P3ConnectionItems} />
        <div className="actions" aria-label="daily command p2 p3 connection actions">
          <a href={dailyCommandP2P3ConnectionPrimaryHref} title={dailyCommandP2P3ConnectionActionBoundary} aria-label="open primary p2 p3 connection action">{dailyCommandP2P3ConnectionPrimaryLabel}</a>
          <a href="#factor" title="切换到股票量化推演；只读回放 P2/P3 本地结果" aria-label="open factor from p2 p3 connection checkpoint">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session from p2 p3 connection checkpoint">次日图谱</a>
          <a href={dailyCommandCandidateConfirmHref} title="回到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from p2 p3 connection checkpoint">确认或换一只票</a>
        </div>
        <p className="risk-note">这张 checkpoint 只合成 CandidateRadar 本地 P2 三面和 P3 可读结果；缺口只显示待回放，不从首页补调 Tushare/DeepSeek，也不创建第二个确认任务。</p>
      </PacketCard>
      <PacketCard title="P2 小数据三面速读" subtitle="确认后直接看本地三面数据是否能回放" status={candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "ready" : "waiting_confirm"}>
        <p className="ordinary-status-note" aria-label="daily command p2 ordinary one line" aria-live="polite">{dailyCommandP2OrdinaryOneLine}</p>
        <p className="ordinary-status-note" aria-label="daily command p2 writeback visible location" aria-live="polite">{dailyCommandP2VisibleWritebackSentence}</p>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "三面状态", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "三面完整度", value: dailyCommandP2SurfaceCompletionLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "缺哪一面", value: dailyCommandP2MissingSurfaceLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "处理建议", value: dailyCommandP2OrdinaryNextAction, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "P2 checkpoint", value: dailyCommandP2CheckpointLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "数据凭证", value: dailyCommandP2CallLedgerState, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "写入面", value: "缓存 / 数据凭证 / 结果包", tone: "good" },
            { label: "来源回执", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
            { label: "下一步", value: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "打开股票量化推演和次日图谱回放" : "确认任务完成后刷新本地三面回放", tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "边界", value: "这张卡只读已有 P2 写回摘要；不创建第二个 task、不补调 Tushare/DeepSeek、不展示 raw log；这张卡只读已有 P2 数据摘要；不重复启动确认链、不补调 Tushare/DeepSeek、不展示原始日志", tone: "good" }
          ]}
        />
        <div aria-label="daily command p2 three surface checkpoint">
          <h3>P2 三面 checkpoint</h3>
          <MetricGrid
            items={[
              { label: "状态", value: dailyCommandP2CheckpointStatus, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
              { label: "速读", value: dailyCommandP2CheckpointLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
              { label: "三面完整度", value: dailyCommandP2SurfaceCompletionLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
              { label: "下一步", value: dailyCommandP2CheckpointNextAction, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
              { label: "边界", value: dailyCommandP2CheckpointBoundary, tone: "good" }
            ]}
          />
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_p2_three_surface_checkpoint：普通用户直接看缓存、数据凭证、结果包三面是否齐，不需要展开原始包或工程审计。</p>
        </div>
        <div aria-label="daily command p2 three surface proof">
          <h3>P2 三面写回证明</h3>
          <MetricGrid items={dailyCommandP2ThreeSurfaceProofItems} />
          <p className="risk-note">这条证明只合成 CandidateRadar 本地 cache 的 cache_ready、ledger_ready、packet_ready 和三面完整度；它不创建 task、不调用 Tushare/DeepSeek、不展示 token/key/raw log；敏感凭据和原始日志也不展示，也不是买卖指令。</p>
        </div>
        <div aria-label="daily command ordinary p2 writeback front row">
          <h3>P2 三面回放</h3>
          <p className="risk-note">确认后直接看 cache、call_ledger、packet 是否能本地回放；优先读取 CandidateRadar 的 ordinary_writeback_surface_summary_rows，让普通用户确认缓存、数据凭证、结果包三面有没有本地回放；完整工程审计仍下沉在折叠明细。</p>
          <DataLineageTable rows={dailyCommandSmallDataWritebackRows} />
        </div>
        <div className="actions" aria-label="daily command p2 writeback front actions">
          <a href="#factor" title="切换到股票量化推演；只读回放本地 P2/P3 结果" aria-label="open factor after p2 writeback front row">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地 P2/P3 图谱" aria-label="open next session after p2 writeback front row">次日图谱</a>
          <a href={dailyCommandCandidateConfirmHref} title="回到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm after p2 writeback front row">确认或换一只票</a>
        </div>
        <p className="risk-note">P2 三面速读只从 CandidateRadar cache / call_ledger / packet 回放；P2 三面速读只从 CandidateRadar 本地三面结果回放；不会从首页回放卡重复启动确认链、读取敏感凭据、执行真实交易或修改交易策略。</p>
      </PacketCard>
      <PacketCard title="P3 可解释结果一眼读懂" subtitle="结论、来源、缺口、下一步和安全边界；只读本地结果检查点" status={dailyCommandP3OneGlanceStatus}>
        <p className="ordinary-status-note" aria-label="daily command p3 ordinary one line" aria-live="polite">{dailyCommandP3OrdinaryOneLine}</p>
        <p className="ordinary-status-note" aria-label="daily command p3 visible explainable result" aria-live="polite">{dailyCommandP3VisibleExplainableSentence}</p>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "一句话结论", value: dailyCommandP3OrdinaryOneLine, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "可读结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "来源读法", value: dailyCommandP3OrdinarySourceLine, tone: dailyCommandP3OneGlanceProviderVerified ? "good" : "warn" },
            { label: "缺口读法", value: dailyCommandP3OrdinaryGapLine, tone: dailyCommandP3ExplainableMissingEvidenceCount ? "warn" : "good" },
            { label: "行动建议", value: dailyCommandP3OrdinaryActionLine, tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good" },
            { label: "数据来源", value: dailyCommandP3OneGlanceSource, tone: dailyCommandP3OneGlanceProviderVerified ? "good" : "warn" },
            { label: "结果证据", value: dailyCommandP3OneGlanceEvidence, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "来源任务", value: dailyCommandP3OneGlanceSourceTask, tone: dailyCommandP3OneGlanceSourceTask === "等待确认回执" ? "warn" : "good" },
            { label: "确认来源", value: dailyCommandP3OneGlanceSourceTask, tone: dailyCommandP3OneGlanceSourceTask === "等待确认回执" ? "warn" : "good" },
            { label: "结果入口", value: dailyCommandP3OneGlanceResultEntrances, tone: candidateQuantHandoffRows.length ? "good" : "warn" },
            { label: "Factor handoff", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "Factor 行数", value: `${String(factorCandidateHandoffRows.length)} 行只读`, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "量化推演入口", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "量化回放", value: `${String(factorCandidateHandoffRows.length)} 行只读`, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "待补缺口", value: dailyCommandP3OneGlanceMissingEvidence, tone: dailyCommandP3MissingEvidenceItems.length ? "warn" : "good" },
            { label: "下一步", value: dailyCommandExplainableResultNext },
            { label: "模型状态", value: dailyCommandP3OneGlanceModelState, tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good" },
            { label: "安全字段", value: dailyCommandP3OneGlanceSafeFields, tone: "good" },
            { label: "安全摘要", value: dailyCommandP3OneGlanceSafeFields, tone: "good" },
            { label: "边界", value: dailyCommandExplainableResultBoundary, tone: "good" }
          ]}
        />
        <details className="developer-audit-details" aria-label="daily command p3 detail tables demoted">
          <summary>P3 详情回放</summary>
          <p className="risk-note">默认先看上方一句话结论、来源、缺口和行动建议；需要复核证据时再展开这些 P3 明细表。</p>
          <div aria-label="daily command p3 explainable result checkpoint">
            <h3>P3 可解释结果检查点</h3>
            <MetricGrid
              items={[
                { label: "状态", value: dailyCommandP3ExplainableCheckpointStatus, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
                { label: "速读", value: dailyCommandP3ExplainableCheckpointLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
                { label: "来源", value: dailyCommandP3OneGlanceSource, tone: dailyCommandP3OneGlanceProviderVerified ? "good" : "warn" },
                { label: "缺口", value: dailyCommandP3OneGlanceMissingEvidence, tone: dailyCommandP3ExplainableMissingEvidenceCount ? "warn" : "good" },
                { label: "下一步", value: dailyCommandP3ExplainableCheckpointNextAction, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
                { label: "边界", value: dailyCommandP3ExplainableCheckpointBoundary, tone: "good" }
              ]}
            />
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_p3_explainable_result_checkpoint：普通用户直接看可读结论、来源、缺口和下一步；DeepSeek 不参与本地结果回放。</p>
          </div>
          <div aria-label="daily command p3 explainable result proof">
            <h3>P3 结果证明</h3>
            <MetricGrid items={dailyCommandP3ExplainableProofItems} />
            <p className="risk-note">这条证明只合成 CandidateRadar 本地 cache 的 P3 checkpoint、可读结论、Tushare-first 来源、缺口和模型状态；这条证明只合成下一票雷达本地结果检查点、可读结论、Tushare-first 来源、缺口和模型状态；不创建 task、不调用 DeepSeek、不展示 raw packet/token/key；原始包和敏感凭据也不展示，也不是买卖指令。</p>
          </div>
          <div aria-label="daily command p3 one glance decision brief">
            <h3>P3 一分钟决策速读</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_decision_brief_rows：先看结论、再看来源、最后看下一步和边界；首页只读本地证据，不创建 task。</p>
            <DataLineageTable rows={dailyCommandP3OneGlanceDecisionRows} />
          </div>
          <div aria-label="daily command p3 one glance quick rows">
            <h3>结果速读全部项</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows 全部项：只看结论、下一步、证据、缺口和边界；只读 `search_quant_projection_result_checkpoint`；不展开 raw packet、不创建 task、不调用 provider/model；不展开原始包。</p>
            <DataLineageTable rows={dailyCommandP3OneGlanceQuickRows} />
          </div>
          <div aria-label="daily command factor candidate handoff readback">
            <h3>股票量化推演 handoff / 入口</h3>
            <p className="risk-note">优先读取 /api/factor-quant/cache 的 ordinary_quant_candidate_handoff_rows：只读确认下一票雷达的确认结果是否已经接到股票量化推演；只读确认 CandidateRadar 确认任务是否已经接到股票量化推演；不创建 task、不补调 provider/model。</p>
            <DataLineageTable rows={dailyCommandFactorCandidateHandoffReadbackRows} />
          </div>
        </details>
        <div className="actions" aria-label="daily command p3 one glance actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；只读查看 P3 结果速读" aria-label="open candidate radar confirm input p3 one glance">下一票雷达确认输入区</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor p3 one glance">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session p3 one glance">次日图谱</a>
        </div>
        <p className="risk-note">这张卡只读本地结果检查点和下一票雷达缓存；不会创建 task、不会调用 DeepSeek、不会交易或修改 strategy action；不会交易或修改交易策略。</p>
      </PacketCard>
      <span hidden title="最近本地任务" />
      <PacketCard title="最近确认进度" subtitle="打开软件后直接看进度；只读本地确认和回放状态" status={dailyCommandLatestTaskStatus}>
        <MetricGrid
          items={[
            { label: "确认记录", value: taskIndex?.task_count ?? tasks.length, tone: (taskIndex?.task_count ?? tasks.length) ? "good" : "warn" },
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "最近确认", value: dailyCommandLatestTaskId || "暂无", tone: dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "状态", value: dailyCommandLatestTaskStatus, tone: dailyCommandLatestTaskStatus === "success" ? "good" : dailyCommandLatestTaskStatus === "failed" ? "bad" : "warn" },
            { label: "按钮链路", value: dailyCommandLatestConfirmReadableStatus, tone: dailyCommandLatestTaskStepLower.includes("blocked_") ? "warn" : dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "处理建议", value: dailyCommandLatestConfirmNextAction, tone: dailyCommandLatestTaskStepLower.includes("blocked_") ? "warn" : dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "确认来源", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
            { label: "回放来源", value: dailyCommandLatestTaskIsReplay ? "本地只读回放" : "本机确认记录", tone: "good" },
            { label: "下一步", value: dailyCommandLatestTaskNext },
            { label: "边界", value: "首页只读最近确认进度；确认按钮之前不启动新确认", tone: "good" }
          ]}
        />
        <DataLineageTable rows={dailyCommandLatestTaskRows} />
        <div className="actions" aria-label="daily command latest local confirm actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入代码后仍需确认按钮" aria-label="open candidate radar confirm input from latest local task">下一票雷达确认代码</a>
          <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读查看最近确认的数据能力缺口" aria-label="open data capability from latest local confirm">数据能力</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor projection from latest local task">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session map from latest local task">次日图谱</a>
          <a href="#tasks" title="切换到进度明细；只读查看完整确认记录" aria-label="open progress details from latest local confirm">进度明细</a>
        </div>
        {dailyCommandLatestTaskId && !dailyCommandLatestTaskIsReplay ? <TaskStatusPanel taskId={dailyCommandLatestTaskId} /> : null}
        {dailyCommandLatestTaskId && dailyCommandLatestTaskIsReplay ? (
          <p className="risk-note">最近确认来自下一票雷达本地只读回放，不启动进度面板轮询；看上方 P1/P2/P3 状态即可。</p>
        ) : null}
        <details className="developer-audit-details" aria-label="daily command latest confirm technical details">
          <summary>本地记录明细</summary>
          <MetricGrid
            items={[
              { label: "本地编号", value: dailyCommandLatestTaskId || "暂无", tone: dailyCommandLatestTaskId ? "good" : "warn" },
              { label: "存储来源", value: dailyCommandLatestTaskSource, tone: "good" },
              { label: "底层接口", value: "/api/tasks 只读回放", tone: "good" }
            ]}
          />
          <p className="risk-note">本卡底层只读 `/api/tasks` 和具体 task 状态；不会补调 Tushare、DeepSeek 或 GitHub，也不会真实交易或修改交易策略。</p>
        </details>
      </PacketCard>
      <details className="developer-audit-details" aria-label="daily command summary and recovery details demoted">
        <summary>本地回放 / 补证明细</summary>
        <p className="risk-note">P4 普通优先：默认只看上方 P0 联通、P1 确认、P2 三面、P3 可解释结果和最近确认进度；这块摘要、恢复表、P5/P6 补证和工程行表需要排障时再展开。</p>
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
          <div aria-label="daily command research route map">
            <h3>今日投研路径</h3>
            <p className="risk-note">打开 app 先按这条路走：确认股票、看候选、查 ETF/融资风险、再看次日图谱；缺数据时显示 pending/degraded，不把空结果当无风险。</p>
            <MetricGrid items={dailyCommandResearchRouteMapItems} />
            <div className="actions" aria-label="daily command research route map actions">
              <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm from daily command route map">确认股票</a>
              <a href="#candidates/candidate-pool" title="切换到下一票候选池；只读本地候选缓存" aria-label="open candidate pool from daily command route map">候选池</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from daily command route map">ETF/融资风险</a>
              <a href="#next/next-session-chart" title="切换到次日图谱；只读本地图谱" aria-label="open next session from daily command route map">次日图谱</a>
            </div>
          </div>
          <DataLineageTable rows={dailyCommandUsableShortestPathPrimaryRows} />
          <div aria-label="daily command p4 ordinary first mode">
            <h3>普通优先模式</h3>
            <p className="risk-note">P4 的当前口径是把工程审计噪音下沉：默认先看 P0-P3 的本地联通、确认按钮、三面写回和可读结果；P4-P6 只在需要排障、补证或 strict closeout 时展开。</p>
            <p className="risk-note">普通优先模式不展示 raw packet、raw log、token/key、provider error 或未脱敏模型输出。</p>
            <MetricGrid items={dailyCommandP4OrdinaryFirstItems} />
          </div>
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
          <a href="#marginEtf" title="切换到 ETF / 融资模块；只读本地风险预算，不生成加融资指令" aria-label="open margin etf from daily command">查看 ETF/融资风险</a>
          <a href="#next" title="切换到次日图谱模块；只回放本地次日图谱缓存，不创建 task" aria-label="open next session map from daily command">查看次日图谱</a>
          <a href="#dataHealth" title="切换到数据健康模块；只读 cache，不刷新外部数据源" aria-label="open data health from daily command">查看数据健康</a>
          <a href="#desktop" title="切换到桌面壳预检模块；只读恢复指引，不启动服务" aria-label="open one click startup preflight from daily command">查看一键启动预检</a>
        </div>
        <p className="risk-note">今日先按“P0 本地联通 → 首页确认股票代码 → 下一票候选池 → ETF/融资风险 → 股票量化推演 / 次日图谱回放”复核；缺数据就看 pending 和缺少证据，不把空结果当成无风险。</p>
        <p className="risk-note">{dailyCommandExternalTriggerBoundary}</p>
        <p className="risk-note">{dailyCommandResultLocation}</p>
        <p className="risk-note">如果本地联通异常，先去 <a href="#desktop">桌面壳预检</a> 查看本地快捷入口；这个跳转只切换页面，不启动 FastAPI/Vite/浏览器。</p>
        <p className="risk-note">这些入口链接只切换本地页面（本地模块路由）；不会创建 task、调用 Tushare/DeepSeek/GitHub、写 cache/config 或改变交易策略。</p>
        <p className="risk-note">live_light 补证入口下沉在开发详情；普通路径只看本地缓存、雷达和量化入口。</p>
        {/* P6 strict closeout 回归入口默认收起；普通回放表先呈现 P0-P3。 */}
        <details className="developer-audit-details" aria-label="daily command ordinary readback details">
          <summary>本地回放明细</summary>
          <p className="risk-note">确认链、P2 写回、P3 检查点和恢复表默认收起；普通用户先用上方主按钮在首页确认股票代码，再看股票量化推演和次日图谱。P6 strict closeout 和完整工程审计在下一层折叠区，不混入普通回放明细。</p>
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
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows：普通入口只看可读结论、来源组成、回放来源和待补证据；不会从 P3 回放卡创建 task、调用 DeepSeek 或展开原始包。</p>
          <DataLineageTable rows={dailyCommandExplainableResultRows} />
        </div>
        <div aria-label="daily command p3 result checkpoint">
          <h3>P3 结果检查点</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_checkpoint_rows：把可读结论、来源状态、待补缺口和安全字段合成首页检查点；只读本地三面结果，不创建 task、不调用模型。</p>
          <DataLineageTable rows={dailyCommandP3CheckpointRows} />
        </div>
        <div aria-label="daily command p3 replay handoff">
          <h3>P3 结果回放入口</h3>
          <p className="risk-note">普通用户按下一票雷达、股票量化推演、次日图谱三步回放；这些入口只切换本地模块，不创建任务、不刷新 provider/model。</p>
          <DataLineageTable rows={dailyCommandP3ReplayActionRows} />
        </div>
        <div aria-label="daily command factor cache fallback readback">
          <h3>量化缓存降级回放</h3>
          <p className="risk-note">如果上次持久化量化 packet 是失败态，首页只读展示安全摘要，并继续使用本地 cache-only 回放；不展开 raw failed packet、provider error、敏感凭据或 call_ledger；也不展开 raw failed packet、provider error、token/key 或 call_ledger。</p>
          <DataLineageTable rows={dailyCommandFactorCacheFallbackRows} />
        </div>
        <div aria-label="daily command p5 deepseek governance quick read">
          <h3>P5 DeepSeek 单独治理</h3>
          <p className="risk-note">优先读取 /api/model-strategy/cache 的 governed_executor；CandidateRadar governance rows 只作 fallback。DeepSeek 只作为 governed executor 单独补证；pending/skipped 不阻塞 Tushare-first、小数据写入或基础图谱。</p>
          <p className="risk-note" aria-label="daily command p5 ordinary one line">{dailyCommandP5OrdinaryOneLine}</p>
          <DataLineageTable rows={dailyCommandP5OrdinaryRows} />
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
        <details className="developer-audit-details" aria-label="daily command engineering audit and strict closeout details">
          <summary>工程审计 / P6 strict closeout 明细</summary>
          <p className="risk-note">普通路径已经在上方 P1 确认、P2 三面和 P3 可解释结果；这里仅供排障、验收和 14 LTG 回归，不把 P6 当今日可用化完成。普通用户先看上方 P1 确认、P2 三面和 P3 可解释结果。</p>
          <div aria-label="daily command p6 strict closeout reentry">
            <h3>P6 strict closeout 回归入口</h3>
            <p className="risk-note">P0-P5 是使用者可用化 checkpoint；14 LTG strict closeout 仍需 current-head direct evidence、CI、浏览器、provider、worker、storage 和 package gate 逐项补证；P6 只是 strict closeout 回归门，不是 14 LTG 完成声明；P4 下沉的是工程审计明细，不压过 P0-P3 普通路径。</p>
            <p className="risk-note" aria-label="daily command p6 ordinary one line">{dailyCommandP6OrdinaryOneLine}</p>
            <DataLineageTable rows={dailyCommandP6StrictCloseoutReentryRows} />
            <div className="actions" aria-label="daily command p6 reentry links">
              <a href="#migration" title="切换到迁移状态页；只读查看 14 LTG direct evidence 缺口" aria-label="open migration status for strict closeout reentry">查看 14 LTG 迁移状态</a>
              <a href="#tasks" title="切换到任务目录；只读回放 task/cache/ledger/packet 证据" aria-label="open task catalog for evidence replay">查看任务和证据回放</a>
            </div>
          </div>
          <div aria-label="daily command local connection readback">
            <h3>本地联通回读复核</h3>
            <p className="risk-note">P6 回归前仍先复核 FastAPI、bootstrap、desktop preflight 和 React/Vite 四段；这里重复只读同一组本地 GET 证据，不启动服务、不创建 task。</p>
            <DataLineageTable rows={dailyCommandStartupReadbackRows} />
          </div>
        </details>
        <p className="risk-note">本地联通状态只读来自 FastAPI health 和 desktop preflight cache；不会启动服务、不会写配置、不会调用 provider/model。</p>
        <p className="risk-note">启动诊断来自 desktop preflight cache：FastAPI /health、bootstrap status、desktop preflight cache 和 React/Vite 前端 HTML 分段检查；首页只展示，不执行。</p>
        <p className="risk-note">恢复回读只看本地 GET health/bootstrap/preflight 结果；如果没有变绿，继续回一键启动预检，不进入投研入口。</p>
        <p className="risk-note">主下一步会在联通异常时优先打开桌面壳预检；这个链接只读本地 health/preflight cache，不启动服务。</p>
        </details>
        <p className="risk-note">工程审计明细默认收起；完整 call ledger、release gate、runtime mode 和配置状态在 <a href="#audit">调用审计</a> / <a href="#settings">配置健康</a>。</p>
      </PacketCard>
      </details>
      </details>
      <details className="developer-audit-details">
        <summary>开发 / 审计详情</summary>
        <p>详细验收记录、开发表格和排障明细默认收起；普通用户先看上方 P0 联通、P1 确认、P2 三面、P3 可解释结果和最近确认进度。</p>
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
        <PacketCard title="次日操作图谱 cache" subtitle="GET cache，不刷新，不改交易策略" status={String(next.status ?? "cache")}>
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
        <PacketCard title="持仓画像 cache" subtitle="GET cache，只读持仓上下文，不改交易策略" status={String(position.status ?? "cache")}>
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
        <PacketCard title="DeepSeek 模型策略" subtitle="独立 cache；不展示敏感凭据，不触发模型调用" status={modelStrategy.contains_secret === true ? "check" : "safe"}>
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
    </div>
  );
}
