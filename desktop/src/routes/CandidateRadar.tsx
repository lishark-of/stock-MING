import { useEffect, useRef, useState } from "react";
import { API_BASE_CANDIDATE_DISPLAY_URLS, API_BASE_DISPLAY_URL, getAuditCache, getBootstrapStatus, getCandidateRadarCache, getDataCapabilityCache, getDesktopPreflightCache, postCandidateRadarBrowserQaReview, postCandidateRadarDeepScanLocalReview, postCandidateRadarDeepScanPlan, postCandidateRadarDeepScanWorker, postCandidateRadarFullPoolLocalScan, postCandidateRadarFullPoolPlan, postCandidateRadarFullPoolWorkerScan, postCandidateRadarLegacyRetirementReview, postCandidateRadarProductionPromotionDryRun, postCandidateRadarProductionPromotionReview, postCandidateRadarProductionReplacementReview, postCandidateRadarProviderParityDryRun, postCandidateRadarQuantProjection, postCandidateRadarQuantProjectionAcceptanceDryRun, postCandidateRadarQuantProjectionExecutionRequest, postCandidateRadarQuantProjectionProviderModelAcceptance, postCandidateRadarQuickScan, postCandidateRadarWorkerExecutionRequest, type TaskCreationEnvelope } from "../api/client";
import { getTasks, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import PageStateBanner from "../components/PageStateBanner";
import StateClarityRail from "../components/StateClarityRail";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function objectRow(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

function displayText(value: unknown, fallback = "--") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function ordinaryUserText(value: unknown, fallback = "--") {
  const text = displayText(value, fallback);
  return text
    .replace(/quant_projection_local_receipt_ready_provider_model_pending/g, "本地结果已记录；数据和模型待补")
    .replace(/\bexplicit_market_suffix\b/g, "需要补全交易所后缀")
    .replace(/\bTaskStatusPanel\b/g, "本地进度面板")
    .replace(/\bPOST task\b/g, "后台流程")
    .replace(/\btask receipt\b/g, "本地确认记录")
    .replace(/\bprovider task\b/g, "数据流程")
    .replace(/\btask id\b/gi, "本地任务编号")
    .replace(/\btask_id\b/g, "本地任务编号")
    .replace(/\btask\b/g, "后台流程")
    .replace(/\bTushare-first\b/g, "数据优先链路")
    .replace(/\bTushare\b/g, "外部行情数据")
    .replace(/\bDeepSeek\b/g, "模型解释")
    .replace(/\bGitHub\b/g, "远端检查")
    .replace(/\bcall_ledger\b/g, "数据记录")
    .replace(/\bledger\b/g, "数据记录")
    .replace(/\bpacket\b/g, "结果包")
    .replace(/\bcache\b/g, "本地缓存")
    .replace(/\breceipt\b/g, "记录")
    .replace(/\bsuccess\b/g, "完成")
    .replace(/\bpending\b/g, "等待中")
    .replace(/\bskipped\b/g, "已跳过")
    .replace(/\bscope hash\b/g, "确认范围编号")
    .replace(/\bpayload\b/g, "请求摘要")
    .replace(/\bstrategy action\b/g, "交易策略")
    .replace(/\bgoverned executor\b/g, "单独治理能力")
    .replace(/\bprovider\b/g, "数据源")
    .replace(/\bmodel\b/g, "模型")
    .replace(/\brelease gate\b/g, "发布门禁")
    .replace(/\bstrict closeout\b/g, "严格收口")
    .replace(/\bcache_missing\b/g, "本地结果未就绪")
    .replace(/\bdegraded\b/g, "待恢复")
    .replace(/\bLTG-\d+\b/g, "长期目标")
    .replace(/\bLTG\b/g, "长期目标")
    .replace(/账本/g, "数据记录");
}

function ordinaryUserMetricItems(items: MetricItem[]) {
  return items.map((item) => ({
    ...item,
    label: ordinaryUserText(item.label),
    value: ordinaryUserText(item.value),
    tone: undefined
  }));
}

function ordinaryUserRows(rowSet: Array<Record<string, unknown>>) {
  return rowSet.map((row) =>
    Object.fromEntries(Object.entries(row).map(([key, value]) => [ordinaryUserText(key), ordinaryUserText(value)]))
  );
}

function readableSentencePart(label: string, value: string, stripPrefixes: string[] = []) {
  let cleaned = value.trim();
  for (const prefix of stripPrefixes) {
    if (cleaned.startsWith(prefix)) {
      cleaned = cleaned.slice(prefix.length).trim();
      break;
    }
  }
  return `${label}：${cleaned}`;
}

function ordinaryResultSurfaceLabel(surface: unknown) {
  const key = String(surface ?? "");
  if (key === "data_source") return "数据来源";
  if (key === "quant_projection") return "量化推演";
  if (key === "next_session_map") return "次日图谱";
  if (key === "research_only_boundary") return "安全边界";
  return displayText(surface, "解释结果");
}

function confirmedTaskReceiptLabel(item: unknown) {
  const key = String(item ?? "");
  if (key === "task_id") return "task_id";
  if (key === "p0_confirm_gate") return "P0 联通闸门";
  if (key === "p1_confirm_contract") return "P1 确认合同";
  if (key === "tushare_first_chain") return "Tushare-first 链路";
  if (key === "safe_current_step") return "安全步骤";
  if (key === "result_destinations") return "结果去向";
  return displayText(item, "确认回执");
}

function quantProjectionSubmitFailureMessage(error?: string | null) {
  if (error === "missing_task_id") {
    return "未生成 task id";
  }
  if (error?.includes("backend_offline_or_unreachable")) {
    return "本地 FastAPI 后端未连接；请先用一键启动器恢复连接。";
  }
  if (error?.includes("frontend_submit_exception")) {
    return "确认按钮请求未完成；请确认本地后端连接后重试。";
  }
  if (error?.startsWith("HTTP ")) {
    return "本地任务接口返回失败；请稍后重试或查看系统健康页。";
  }
  return "任务未创建；请检查本地后端连接后重试。";
}

function normalizeAshareSymbolInput(raw: string) {
  const input = raw.trim().toUpperCase().replace(/\s+/g, "");
  if (!input) {
    return { input, normalized: "", valid: false, reason: "empty_symbol" };
  }
  const explicit = input.match(/^(\d{6})\.(SH|SZ|BJ)$/);
  if (explicit) {
    return { input, normalized: `${explicit[1]}.${explicit[2]}`, valid: true, reason: "explicit_market_suffix" };
  }
  const digits = input.match(/^(\d{6})$/);
  if (!digits) {
    return { input, normalized: "", valid: false, reason: "require_6_digits_or_suffix" };
  }
  const symbol = digits[1];
  const inferredMarket = /^(60|68|90)/.test(symbol)
    ? "SH"
    : /^(00|30|20)/.test(symbol)
      ? "SZ"
      : /^(43|83|87|88|92)/.test(symbol)
        ? "BJ"
        : "";
  if (!inferredMarket) {
    return { input, normalized: "", valid: false, reason: "unsupported_a_share_prefix" };
  }
  return { input, normalized: `${symbol}.${inferredMarket}`, valid: true, reason: "inferred_market_suffix" };
}

function candidateRadarRouteAnchorFromHash() {
  if (typeof window === "undefined") return "";
  const cleaned = window.location.hash.trim().replace(/^#\/?/, "");
  const parts = cleaned.split("/");
  return parts.length > 1 ? parts.slice(1).join("/").split("?")[0] : "";
}

const DATA_CAPABILITY_HREF = "#dataCapability";

export default function CandidateRadar() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [auditCache, setAuditCache] = useState<Record<string, unknown>>({});
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [bootstrapEnvelopeLedger, setBootstrapEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [bootstrapEnvelopeWarnings, setBootstrapEnvelopeWarnings] = useState<Array<string>>([]);
  const [desktopPreflight, setDesktopPreflight] = useState<Record<string, unknown>>({});
  const [desktopPreflightEnvelopeLedger, setDesktopPreflightEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [dataCapabilityCache, setDataCapabilityCache] = useState<Record<string, unknown>>({});
  const [dataCapabilityEnvelopeLedger, setDataCapabilityEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [quantProjectionSubmitting, setQuantProjectionSubmitting] = useState(false);
  const [quantProjectionSubmitError, setQuantProjectionSubmitError] = useState("");
  const [customPoolText, setCustomPoolText] = useState("");
  const [searchSymbol, setSearchSymbol] = useState("");
  const [searchSymbolTouched, setSearchSymbolTouched] = useState(false);
  const [leadCandidatePrefillSymbol, setLeadCandidatePrefillSymbol] = useState("");
  const searchSymbolRef = useRef("");
  const searchSymbolTouchedRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const quantProjectionP1ConfirmPayloadContract = {
    schema_version: "candidate_radar_p1_confirm_button_contract.v1",
    source: "candidate_radar_confirm_button",
    trigger: "explicit_user_click",
    input_before_confirm_creates_task: false,
    search_input_external_calls: false,
    react_render_external_calls: false,
    get_cache_external_calls: false,
    include_tushare_first: true,
    include_deepseek: true,
    deepseek_policy: "governed_explanation_only_safe_degraded",
    requires_p0_gate_ready: true,
    p0_gate_surfaces: ["fastapi_cache_get", "bootstrap_runtime_mode", "desktop_preflight_one_click_packet", "p0_stability_or_local_link_evidence", "candidate_cache_get_readable"],
    writeback_surfaces: ["cache", "call_ledger", "packet"],
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
  };
  const updateSearchSymbolInput = (value: string, source: "manual" | "lead_candidate_prefill" = "manual") => {
    searchSymbolRef.current = value;
    searchSymbolTouchedRef.current = true;
    setSearchSymbol(value);
    setSearchSymbolTouched(true);
    setLeadCandidatePrefillSymbol(source === "lead_candidate_prefill" ? value : "");
  };
  const prefillSearchSymbolFromCache = (value: string) => {
    searchSymbolRef.current = value;
    setSearchSymbol(value);
  };

  const refreshCache = () => {
    setLoading(true);
    setError("");
    void getCandidateRadarCache()
      .then((res) => {
        setCache(res.data);
        setCacheEnvelopeLedger(res.call_ledger ?? []);
        setCacheEnvelopeWarnings(res.warnings ?? []);
        const cachedQuantProjectionReceipt =
          (res.data.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
        const cachedQuantProjectionSymbol = String(cachedQuantProjectionReceipt.symbol ?? "");
        if (
          !searchSymbolTouched &&
          !searchSymbolTouchedRef.current &&
          !searchSymbolRef.current.trim() &&
          normalizeAshareSymbolInput(cachedQuantProjectionSymbol).valid
        ) {
          prefillSearchSymbolFromCache(cachedQuantProjectionSymbol);
        }
        if (res.ok === false) setError(res.error ?? "candidate_radar_cache_not_ok");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  };
  const refreshBootstrapStatus = () => {
    void getBootstrapStatus().then((res) => {
      setBootstrapStatus(res.data);
      setBootstrapEnvelopeLedger(res.call_ledger ?? []);
      setBootstrapEnvelopeWarnings(res.warnings ?? []);
    });
  };
  const refreshTaskIndex = () => {
    void getTasks().then((res) => setTaskIndex(res.data));
  };
  const refreshAuditCache = () => {
    void getAuditCache().then((res) => setAuditCache(res.data));
  };
  const refreshDataCapabilityCache = () => {
    void getDataCapabilityCache().then((res) => {
      setDataCapabilityCache(res.data);
      setDataCapabilityEnvelopeLedger(res.call_ledger ?? []);
    });
  };
  const refreshQuantProjectionReadback = () => {
    refreshCache();
    refreshBootstrapStatus();
    refreshTaskIndex();
    refreshAuditCache();
    refreshDataCapabilityCache();
  };
  const refreshDesktopPreflight = () => {
    void getDesktopPreflightCache().then((res) => {
      setDesktopPreflight(res.data);
      setDesktopPreflightEnvelopeLedger(res.call_ledger ?? []);
    });
  };
  const launchQuickScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "quick_cache_scan", universe_mode: "cache_snapshot" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchQuantProjection = () => {
    if (!quantProjectionCanSubmit || quantProjectionSubmitting) return;
    setQuantProjectionSubmitting(true);
    setQuantProjectionSubmitError("");
    void postCandidateRadarQuantProjection({
      scan_mode: "search_quant_projection",
      symbol: normalizeAshareSymbolInput(searchSymbol).normalized,
      include_tushare: true,
      include_deepseek: true,
      deepseek_policy: "governed_explanation_only_safe_degraded",
      user_approved: true,
      requested_by: "candidate_radar_page",
      p0_confirm_gate_evidence: {
        schema_version: "candidate_radar_p0_confirm_gate.v1",
        p0_ready: quantProjectionConfirmGateReady,
        fastapi_cache_get_ready: quantProjectionLocalAppReady,
        bootstrap_runtime_mode_ready: bootstrapRuntimeModeReady,
        p0_runtime_mode_or_handoff_ready: desktopP0RuntimeModeOrHandoffReady || quantProjectionLocalAppReady,
        desktop_preflight_ready: desktopPreflightReady,
        p0_runtime_packets_ready: desktopP0RuntimePacketsReady || quantProjectionLocalAppReady,
        p0_stability_check_ready: desktopP0StabilityReady,
        p0_local_link_ready: desktopP0LocalLinkReady,
        p0_connection_evidence_ready: desktopP0ConnectionEvidenceReady || quantProjectionLocalAppReady,
        p0_quick_action_ready: desktopP0QuickActionReady,
        p0_contract_evidence_ready: desktopP0ContractEvidenceReady || quantProjectionLocalAppReady,
        p0_readback_ready: quantProjectionP0ReadbackReady,
        p0_local_link_is_ui_gate_only_not_release_evidence: desktopP0LocalLinkReady && !desktopP0StabilityReady,
        candidate_cache_ready: candidateRadarCacheGetReadable,
        candidate_cache_required_for_confirm_button: false,
        candidate_cache_status: String(cache.status ?? "missing"),
        bootstrap_packet_key: String(bootstrapStatus.packet_key ?? "missing"),
        desktop_preflight_packet_key: String(desktopPreflight.packet_key ?? "missing"),
        creates_task_only_after_button: true,
        react_render_external_calls: false,
        get_cache_external_calls: false,
        contains_secret: false,
        contains_sensitive_material: false
      },
      ordinary_confirm_chain_contract: quantProjectionP1ConfirmPayloadContract
    }).then((res) => {
      const acceptedTaskId = String(res.data?.task_id ?? res.data?.task?.task_id ?? "");
      if (res.ok && acceptedTaskId) {
        setTaskReceipt(res);
        setQuantProjectionSubmitError("");
        setTaskId(acceptedTaskId);
        refreshQuantProjectionReadback();
      } else if (res.ok) {
        setTaskId("");
        setTaskReceipt(null);
        setQuantProjectionSubmitError(quantProjectionSubmitFailureMessage("missing_task_id"));
      } else {
        setTaskId("");
        setTaskReceipt(res);
        setQuantProjectionSubmitError(quantProjectionSubmitFailureMessage(res.error));
      }
    }).catch(() => {
      setTaskId("");
      setTaskReceipt(null);
      setQuantProjectionSubmitError(quantProjectionSubmitFailureMessage("frontend_submit_exception"));
    }).finally(() => setQuantProjectionSubmitting(false));
  };
  const launchQuantProjectionAcceptanceDryRun = () =>
    void postCandidateRadarQuantProjectionAcceptanceDryRun({
      scan_mode: "search_quant_projection",
      symbol: normalizeAshareSymbolInput(searchSymbol).normalized || String(searchQuantProjectionReceipt.symbol ?? ""),
      include_tushare: true,
      include_deepseek: true,
      user_approved: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProviderParityDryRun = () =>
    void postCandidateRadarProviderParityDryRun({
      scan_mode: "provider_parity_dry_run",
      candidate_symbols: searchSymbol || String(searchQuantProjectionReceipt.symbol ?? ""),
      selected_signal_groups: ["moneyflow", "dragon_tiger", "limit_emotion", "chip_radar", "hard_risk"],
      include_tushare: true,
      include_deepseek: true,
      user_approved: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchWatchlistScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "watchlist_scan", universe_mode: "local_watchlist" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchCustomScan = () =>
    void postCandidateRadarQuickScan({
      scan_mode: "custom_pool_scan",
      universe_mode: "manual_input",
      custom_pool_text: customPoolText
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolPlan = () =>
    void postCandidateRadarFullPoolPlan({ scan_mode: "full_pool_scan", plan_only: true }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolLocalScan = () =>
    void postCandidateRadarFullPoolLocalScan({ scan_mode: "full_pool_local_scan", local_execution_only: true }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanPlan = () =>
    void postCandidateRadarDeepScanPlan({ scan_mode: "deep_scan", plan_only: true, scan_depth: "legacy_parity_first" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanLocalReview = () =>
    void postCandidateRadarDeepScanLocalReview({ scan_mode: "deep_scan_local_review", local_review_only: true, scan_depth: "legacy_parity_first" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchBrowserQaReview = () =>
    void postCandidateRadarBrowserQaReview({ review_scope: "candidate_route_browser_qa_local_artifact" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
    refreshBootstrapStatus();
    refreshDesktopPreflight();
    refreshTaskIndex();
    refreshAuditCache();
    refreshDataCapabilityCache();
  }, []);
  useEffect(() => {
    const anchor = candidateRadarRouteAnchorFromHash();
    if (anchor !== "candidate-radar-search-quant-projection") return;
    document.getElementById(anchor)?.scrollIntoView({ block: "start" });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const userRouteQaEvidence = (auditCache.user_route_qa_evidence_contract as Record<string, unknown> | undefined) ?? {};
  const userRouteQaCoveredRoutes = Array.isArray(userRouteQaEvidence.covered_routes)
    ? (userRouteQaEvidence.covered_routes as unknown[]).map((route) => String(route))
    : [];
  const userRouteQaCoveredViewports = Array.isArray(userRouteQaEvidence.covered_viewports)
    ? (userRouteQaEvidence.covered_viewports as unknown[]).map((viewport) => String(viewport))
    : [];
  const userRouteQaLatestPassedCount = Number(userRouteQaEvidence.latest_report_passed_count ?? 0);
  const userRouteQaLatestMatrixCount = Number(userRouteQaEvidence.latest_report_qa_matrix_count ?? 0);
  const userRouteQaLatestReviewRequiredCount = Number(userRouteQaEvidence.latest_report_review_required_count ?? 0);
  const userRouteQaLatestConsoleErrorCount = Number(userRouteQaEvidence.latest_report_console_error_count ?? 0);
  const userRouteQaTaskSilenceFailedCount = Number(userRouteQaEvidence.task_silence_failed_count ?? 0);
  const candidateRadarUserRouteQaPassed =
    userRouteQaEvidence.latest_report_candidate_route_passed === true ||
    userRouteQaEvidence.candidate_route_visual_qa_passed === true;
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const scanCoverage = (cache.scan_coverage as Record<string, unknown> | undefined) ?? {};
  const coverageDetail = (cache.coverage_detail_summary as Record<string, unknown> | undefined) ?? {};
  const scanExecutionSummary = (cache.scan_execution_summary as Record<string, unknown> | undefined) ?? {};
  const quickScanReceipt = (cache.quick_scan_execution_receipt as Record<string, unknown> | undefined) ?? {};
  const fastScanTaskPipeline = (cache.fast_scan_task_pipeline_contract as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionReceipt = (cache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionActivation = (cache.search_quant_projection_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionAcceptanceDryRun = (cache.search_quant_projection_acceptance_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionExecutionRequest = (cache.search_quant_projection_execution_request_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProviderModelAcceptance = (cache.search_quant_provider_model_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantDeepSeekExplanation = (cache.search_quant_deepseek_explanation as Record<string, unknown> | undefined) ?? {};
  const searchQuantDeepSeekModelLedger = (cache.search_quant_deepseek_model_ledger as Record<string, unknown> | undefined) ?? {};
  const searchQuantDeepSeekPayload = (searchQuantDeepSeekExplanation.payload as Record<string, unknown> | undefined) ?? {};
  const searchQuantCanonicalResultLineage =
    (cache.search_quant_canonical_result_lineage as Record<string, unknown> | undefined) ??
    (searchQuantProviderModelAcceptance.canonical_result_lineage as Record<string, unknown> | undefined) ??
    {};
  const searchQuantResultLineage =
    Object.keys(searchQuantCanonicalResultLineage).length
      ? searchQuantCanonicalResultLineage
      : (cache.search_quant_current_result_lineage as Record<string, unknown> | undefined) ??
        (cache.search_quant_result_lineage as Record<string, unknown> | undefined) ??
        (searchQuantProviderModelAcceptance.result_lineage as Record<string, unknown> | undefined) ??
        {};
  const searchQuantCurrentResultLineage =
    (cache.search_quant_current_result_lineage as Record<string, unknown> | undefined) ?? {};
  const searchQuantLastGoodResultLineage =
    (cache.search_quant_last_good_result_lineage as Record<string, unknown> | undefined) ?? {};
  const searchQuantDegradedResultLineage =
    (cache.search_quant_degraded_result_lineage as Record<string, unknown> | undefined) ?? {};
  const searchQuantResultVersionSummary =
    (cache.search_quant_result_version_summary as Record<string, unknown> | undefined) ??
    (searchQuantProviderModelAcceptance.result_version_summary as Record<string, unknown> | undefined) ??
    {};
  const searchQuantResultOutputPacketKeys = Array.isArray(searchQuantResultLineage.output_packet_keys)
    ? searchQuantResultLineage.output_packet_keys.map((item) => String(item)).filter(Boolean)
    : [];
  const searchQuantResultInputPacketKeys = Array.isArray(searchQuantResultLineage.input_packet_keys)
    ? searchQuantResultLineage.input_packet_keys.map((item) => String(item)).filter(Boolean)
    : [];
  const searchQuantResultSummaryProviderLedgerIds = Array.isArray(searchQuantResultVersionSummary.latest_task_provider_call_ledger_ids)
    ? searchQuantResultVersionSummary.latest_task_provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
    : Array.isArray(searchQuantResultVersionSummary.degraded_provider_call_ledger_ids)
      ? searchQuantResultVersionSummary.degraded_provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
      : [];
  const searchQuantResultProviderLedgerIds = Array.isArray(searchQuantResultLineage.provider_call_ledger_ids)
    ? searchQuantResultLineage.provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
    : searchQuantResultSummaryProviderLedgerIds;
  const searchQuantResultProviderLedgerLabel = searchQuantResultProviderLedgerIds.length
    ? `${searchQuantResultProviderLedgerIds.length} 条 provider ledger：${searchQuantResultProviderLedgerIds.slice(0, 4).join(" / ")}${searchQuantResultProviderLedgerIds.length > 4 ? " / ..." : ""}`
    : "等待 provider ledger id";
  const searchQuantProjectionSmallDataWriteback = (cache.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionConfirmChainCheckpoint =
    (cache.search_quant_projection_confirm_chain_checkpoint as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionSmallDataReadbackCheckpoint =
    (cache.search_quant_projection_small_data_readback_checkpoint as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionWritebackCheckpoint =
    (cache.search_quant_projection_writeback_checkpoint as Record<string, unknown> | undefined) ??
    (searchQuantProjectionSmallDataWriteback.ordinary_writeback_checkpoint_contract as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionP1ShortestPathCheckpoint =
    (cache.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ??
    (searchQuantProjectionSmallDataWriteback.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionP2ThreeSurfaceCheckpoint =
    (cache.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ??
    (searchQuantProjectionSmallDataWriteback.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionInterpretation = (cache.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionResultCheckpoint =
    (cache.search_quant_projection_result_checkpoint as Record<string, unknown> | undefined) ??
    (searchQuantProjectionInterpretation.ordinary_result_checkpoint_contract as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionP3ExplainableResultCheckpoint =
    (cache.ordinary_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ??
    (cache.search_quant_projection_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ??
    (searchQuantProjectionInterpretation.ordinary_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionPostConfirmOneGlanceItems =
    rows(cache.search_quant_projection_post_confirm_one_glance_items).length
      ? rows(cache.search_quant_projection_post_confirm_one_glance_items)
      : rows(searchQuantProjectionInterpretation.ordinary_post_confirm_one_glance_items);
  const providerParityDryRun = (cache.provider_parity_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const fastScanRuntimeBudget = (cache.fast_scan_runtime_budget_contract as Record<string, unknown> | undefined) ?? {};
  const fastScanReadinessAudit = (cache.fast_scan_readiness_audit as Record<string, unknown> | undefined) ?? {};
  const noFeatureLossAcceptance = (cache.no_feature_loss_acceptance_contract as Record<string, unknown> | undefined) ?? {};
  const replacementGapTriage = (cache.replacement_gap_triage_contract as Record<string, unknown> | undefined) ?? {};
  const promotionBlockerAudit = (cache.candidate_radar_promotion_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const activationReceipt = (cache.candidate_radar_production_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const nextExecutionRecipe = (cache.candidate_radar_next_execution_recipe as Record<string, unknown> | undefined) ?? {};
  const workerExecutionRecipe = (cache.candidate_radar_worker_execution_recipe as Record<string, unknown> | undefined) ?? {};
  const workerExecutionRequest = (cache.candidate_radar_worker_execution_request_receipt as Record<string, unknown> | undefined) ?? {};
  const fullPoolWorkerFallback = (cache.candidate_radar_full_pool_worker_fallback_receipt as Record<string, unknown> | undefined) ?? {};
  const deepScanWorkerFallback = (cache.candidate_radar_deep_scan_worker_fallback_receipt as Record<string, unknown> | undefined) ?? {};
  const workerRuntimeLinkedEvidence = (cache.candidate_radar_worker_runtime_linked_evidence as Record<string, unknown> | undefined) ?? {};
  const productionReplacementReview = (cache.candidate_radar_production_replacement_review_receipt as Record<string, unknown> | undefined) ?? {};
  const productionPromotionDryRun = (cache.candidate_radar_production_promotion_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const legacyRetirementReview = (cache.candidate_radar_legacy_retirement_review_receipt as Record<string, unknown> | undefined) ?? {};
  const productionPromotionReview = (cache.candidate_radar_production_promotion_review_receipt as Record<string, unknown> | undefined) ?? {};
  const launchQuantProjectionExecutionRequest = () =>
    void postCandidateRadarQuantProjectionExecutionRequest({
      scan_mode: "quant_projection_execution_request",
      operator_approved: true,
      acceptance_scope_hash: String(searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchQuantProjectionProviderModelAcceptance = () =>
    void postCandidateRadarQuantProjectionProviderModelAcceptance({
      scan_mode: "quant_projection_provider_model_acceptance",
      operator_approved: true,
      acceptance_scope_hash: String(searchQuantProjectionExecutionRequest.acceptance_scope_hash ?? ""),
      include_deepseek: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchQuantProjectionDeepSeekFailureAcceptance = () =>
    void postCandidateRadarQuantProjectionProviderModelAcceptance({
      scan_mode: "quant_projection_provider_model_acceptance",
      operator_approved: true,
      acceptance_scope_hash: String(searchQuantProjectionExecutionRequest.acceptance_scope_hash ?? ""),
      include_deepseek: true,
      deepseek_failure_mode_for_acceptance: "missing_server_key",
      requested_by: "candidate_radar_page_deepseek_failure_acceptance"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchWorkerExecutionRequest = () =>
    void postCandidateRadarWorkerExecutionRequest({
      scan_mode: "worker_execution_request",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolWorkerFallback = () =>
    void postCandidateRadarFullPoolWorkerScan({
      scan_mode: "full_pool_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRequest.worker_execution_scope_hash ?? workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanWorkerFallback = () =>
    void postCandidateRadarDeepScanWorker({
      scan_mode: "deep_scan_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRequest.worker_execution_scope_hash ?? workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionReplacementReview = () =>
    void postCandidateRadarProductionReplacementReview({
      review_scope: "candidate_radar_production_replacement_local_review",
      approved_by_user: true,
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionPromotionDryRun = () =>
    void postCandidateRadarProductionPromotionDryRun({
      promotion_scope: "candidate_radar_production_promotion_local_dry_run",
      operator_approved: true,
      review_scope_hash: String(productionReplacementReview.review_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchLegacyRetirementReview = () =>
    void postCandidateRadarLegacyRetirementReview({
      review_scope: "candidate_radar_legacy_retirement_local_review",
      operator_approved: true,
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionPromotionReview = () =>
    void postCandidateRadarProductionPromotionReview({
      review_scope: "candidate_radar_production_promotion_local_review",
      operator_approved: true,
      promotion_scope_hash: String(productionPromotionDryRun.promotion_scope_hash ?? ""),
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const durableEvidenceRecipe = (cache.candidate_radar_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {};
  const productionStageScopeManifest = (cache.candidate_radar_production_stage_scope_manifest as Record<string, unknown> | undefined) ?? {};
  const resultDeltaClarity = (cache.result_delta_clarity_contract as Record<string, unknown> | undefined) ?? {};
  const candidatePriorityExplanation = (cache.candidate_priority_explanation_contract as Record<string, unknown> | undefined) ?? {};
  const coarseFineScreening = (cache.coarse_fine_screening_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaRunbook = (cache.candidate_browser_qa_runbook_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaEvidence = (cache.candidate_browser_qa_evidence_summary as Record<string, unknown> | undefined) ?? {};
  const browserQaReview = (cache.candidate_browser_qa_review_contract as Record<string, unknown> | undefined) ?? {};
  const freshnessState = (cache.freshness_state as Record<string, unknown> | undefined) ?? {};
  const fullPoolPlan = (cache.full_pool_scan_plan as Record<string, unknown> | undefined) ?? {};
  const fullPoolLocalExecutionReceipt = (cache.full_pool_local_execution_receipt as Record<string, unknown> | undefined) ?? {};
  const deepScanPlan = (cache.deep_scan_plan as Record<string, unknown> | undefined) ?? {};
  const deepScanLocalReviewReceipt = (cache.deep_scan_local_review_receipt as Record<string, unknown> | undefined) ?? {};
  const legacyParityInventory = (cache.legacy_parity_inventory as Record<string, unknown> | undefined) ?? {};
  const legacyParityAcceptanceReceipt = (cache.legacy_parity_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const localPoolAudit = (cache.local_candidate_pool_audit as Record<string, unknown> | undefined) ?? {};
  const overview = (cache.candidate_execution_evidence_overview as Record<string, unknown> | undefined) ?? {};
  const radarPacket = (cache.radar_packet as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const dataCapabilityProviderCards = rows(dataCapabilityCache.provider_cards);
  const dataCapabilityTushareCard = dataCapabilityProviderCards.find(
    (card) => displayText(card.provider, "").toLowerCase() === "tushare"
  ) ?? {};
  const dataCapabilityTushareAvailableCount = Number(dataCapabilityTushareCard.available_count ?? 0);
  const dataCapabilityTushareRestrictedCount = Number(dataCapabilityTushareCard.restricted_count ?? 0);
  const dataCapabilityTusharePendingCount = Number(dataCapabilityTushareCard.pending_count ?? 0);
  const dataCapabilityPayloadLedger = rows(dataCapabilityCache.call_ledger);
  const dataCapabilityEvidenceLedgerCount = dataCapabilityPayloadLedger.length + dataCapabilityEnvelopeLedger.length;
  const dataCapabilityMode = displayText(dataCapabilityCache.mode ?? "cache_only");
  const dataCapabilityModeLabel = dataCapabilityMode === "cache_only"
    ? "只读缓存模式（不外联）"
    : `${dataCapabilityMode}（按页面边界复核）`;
  const dataCapabilityDegradedState = dataCapabilityTushareRestrictedCount
    ? "受限：存在权限或配置缺口，不能当作无数据"
    : dataCapabilityTusharePendingCount
      ? "待补：存在空窗口、缓存或待补接口，先按保守处理"
      : dataCapabilityTushareAvailableCount
        ? "可读：已有本地数据记录可回放"
        : "等待：暂无本地数据健康记录";
  const dataCapabilityEvidenceLedgerLabel = dataCapabilityEvidenceLedgerCount
    ? `确认范围 ${dataCapabilityPayloadLedger.length} 条；结果来源 ${dataCapabilityEnvelopeLedger.length} 条本地数据记录`
    : "等待本地数据记录回读";
  const candidateRadarPostConfirmDataCapabilitySentence =
    `确认股票后旁边先看数据能力：${dataCapabilityDegradedState}；真实数据补证仍需单独授权，本页不会自动补调。`;
  const candidateRadarPostConfirmDataCapabilityItems: MetricItem[] = [
    {
      label: "数据卡状态",
      value: dataCapabilityDegradedState,
      tone: dataCapabilityTushareRestrictedCount || dataCapabilityTusharePendingCount ? "warn" : dataCapabilityTushareAvailableCount ? "good" : "neutral"
    },
    {
      label: "运行模式",
      value: dataCapabilityModeLabel,
      tone: dataCapabilityCache.cache_only === false ? "bad" : "good"
    },
    {
      label: "证据血缘",
      value: dataCapabilityEvidenceLedgerLabel,
      tone: dataCapabilityEvidenceLedgerCount ? "good" : "warn"
    },
    {
      label: "补证缺口",
      value: "真实数据补证仍需单独授权；本页不会自动补调",
      tone: "warn"
    },
    {
      label: "结果旁边看",
      value: "确认结果、量化推演、次日图谱旁边同步复核权限、空窗口和待补原因",
      tone: "good"
    },
    {
      label: "安全边界",
      value: "数据能力页只读；不创建后台流程、不刷新外部数据或模型、不交易",
      tone: "good"
    }
  ];
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const legacySignalRows = rows(cache.legacy_signal_group_rows);
  const legacyParityRows = rows(cache.legacy_parity_rows);
  const legacyOutputRows = rows(cache.legacy_output_contract_rows);
  const legacyParityAcceptanceRows = rows(cache.legacy_parity_acceptance_rows);
  const scanModeRows = rows(cache.scan_mode_status_rows);
  const scanAcceptanceRows = rows(cache.scan_acceptance_rows);
  const quickScanReceiptRows = rows(cache.quick_scan_execution_receipt_rows);
  const fastScanTaskPipelineRows = rows(cache.fast_scan_task_pipeline_rows);
  const searchQuantProjectionRows = rows(cache.search_quant_projection_rows);
  const searchQuantProjectionActivationRows = rows(cache.search_quant_projection_activation_rows);
  const searchQuantProjectionAcceptanceDryRunRows = rows(cache.search_quant_projection_acceptance_dry_run_rows);
  const searchQuantProjectionCredentialRows = rows(cache.search_quant_projection_credential_presence_rows);
  const searchQuantProjectionExecutionRequestRows = rows(cache.search_quant_projection_execution_request_rows);
  const providerParityDryRunRows = rows(cache.provider_parity_dry_run_rows);
  const providerParityCredentialRows = rows(cache.provider_parity_credential_presence_rows);
  const fastScanRuntimeBudgetRows = rows(cache.fast_scan_runtime_budget_rows);
  const fastScanReadinessRows = rows(cache.fast_scan_readiness_rows);
  const noFeatureLossAcceptanceRows = rows(cache.no_feature_loss_acceptance_rows);
  const replacementGapTriageRows = rows(cache.replacement_gap_triage_rows);
  const promotionBlockerRows = rows(cache.candidate_radar_promotion_blocker_rows);
  const activationReceiptRows = rows(cache.candidate_radar_production_activation_rows);
  const nextExecutionRecipeRows = rows(cache.candidate_radar_next_execution_rows);
  const workerExecutionRows = rows(cache.candidate_radar_worker_execution_rows);
  const workerExecutionRequestRows = rows(cache.candidate_radar_worker_execution_request_rows);
  const fullPoolWorkerFallbackRows = rows(cache.candidate_radar_full_pool_worker_fallback_rows);
  const deepScanWorkerFallbackRows = rows(cache.candidate_radar_deep_scan_worker_fallback_rows);
  const workerRuntimeLinkedRows = rows(cache.candidate_radar_worker_runtime_link_rows);
  const productionReplacementReviewRows = rows(cache.candidate_radar_production_replacement_review_rows);
  const productionPromotionDryRunRows = rows(cache.candidate_radar_production_promotion_dry_run_rows);
  const legacyRetirementReviewRows = rows(cache.candidate_radar_legacy_retirement_review_rows);
  const productionPromotionReviewRows = rows(cache.candidate_radar_production_promotion_review_rows);
  const durableEvidenceRows = rows(cache.candidate_radar_durable_evidence_rows);
  const productionStageScopeRows = rows(cache.candidate_radar_production_stage_scope_rows);
  const resultDeltaClarityRows = rows(cache.result_delta_clarity_rows);
  const previousCacheDiffRows = rows(cache.previous_cache_diff_rows);
  const candidatePriorityExplanationRows = rows(cache.candidate_priority_explanation_rows);
  const coarseScreeningRows = rows(cache.coarse_screening_rows);
  const fineScreeningRows = rows(cache.fine_screening_rows);
  const topWatchExcludedGroupRows = rows(cache.top_watch_excluded_group_rows);
  const browserQaRunbookRows = rows(cache.candidate_browser_qa_runbook_rows);
  const browserQaMatrixRows = rows(cache.candidate_browser_qa_matrix_rows);
  const browserQaEvidenceRows = rows(cache.candidate_browser_qa_evidence_rows);
  const browserQaReviewRows = rows(cache.candidate_browser_qa_review_rows);
  const providerCoverageRows = rows(cache.provider_coverage_rows);
  const degradedModeRows = rows(cache.degraded_mode_rows);
  const bootstrapLiveLight = (bootstrapStatus.live_light as Record<string, unknown> | undefined) ?? {};
  const bootstrapRuntimeOperatorSummary = (bootstrapStatus.runtime_operator_summary_contract as Record<string, unknown> | undefined) ?? {};
  const bootstrapPolicy = (bootstrapStatus.policy as Record<string, unknown> | undefined) ?? {};
  const bootstrapProviderModelEnablementRows = [
    {
      surface: "operator_summary_contract",
      visible: bootstrapRuntimeOperatorSummary.provider_model_enablement_summary_visible === true,
      source_config: bootstrapRuntimeOperatorSummary.provider_model_enablement_source_config,
      configured: bootstrapRuntimeOperatorSummary.provider_model_enablement_configured === true,
      effective: bootstrapRuntimeOperatorSummary.provider_model_enablement_effective === true,
      requires_live_light: bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_live_light === true,
      requires_execution_request: bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_execution_request === true,
      requires_promotion: bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_promotion === true,
      creates_task: bootstrapRuntimeOperatorSummary.provider_model_enablement_creates_task === true,
      creates_provider_model_task: bootstrapRuntimeOperatorSummary.provider_model_enablement_creates_provider_model_task === true,
      calls_provider_model_now: bootstrapRuntimeOperatorSummary.provider_model_enablement_calls_provider_model_now === true,
      frontend_writeback_allowed: bootstrapRuntimeOperatorSummary.provider_model_enablement_frontend_writeback_allowed === true,
      production_evidence: bootstrapRuntimeOperatorSummary.provider_model_enablement_summary_is_production_evidence === true,
    },
    {
      surface: "live_light_flat_summary",
      visible: bootstrapLiveLight.runtime_operator_provider_model_enablement_summary_visible === true,
      source_config: bootstrapLiveLight.runtime_operator_provider_model_enablement_source_config,
      configured: bootstrapLiveLight.runtime_operator_provider_model_enablement_configured === true,
      effective: bootstrapLiveLight.runtime_operator_provider_model_enablement_effective === true,
      requires_live_light: bootstrapLiveLight.runtime_operator_provider_model_enablement_requires_live_light === true,
      requires_execution_request: bootstrapLiveLight.runtime_operator_provider_model_enablement_requires_execution_request === true,
      requires_promotion: bootstrapLiveLight.runtime_operator_provider_model_enablement_requires_promotion === true,
      creates_provider_model_task: bootstrapLiveLight.runtime_operator_provider_model_enablement_creates_provider_model_task === true,
      calls_provider_model_now: bootstrapLiveLight.runtime_operator_provider_model_enablement_calls_provider_model_now === true,
      production_evidence: bootstrapLiveLight.runtime_operator_provider_model_enablement_is_production_evidence === true,
    },
    {
      surface: "policy_flat_summary",
      visible: bootstrapPolicy.runtime_operator_provider_model_enablement_summary_visible === true,
      source_config: bootstrapPolicy.runtime_operator_provider_model_enablement_source_config,
      configured: bootstrapPolicy.runtime_operator_provider_model_enablement_configured === true,
      effective: bootstrapPolicy.runtime_operator_provider_model_enablement_effective === true,
      requires_live_light: bootstrapPolicy.runtime_operator_provider_model_enablement_requires_live_light === true,
      requires_execution_request: bootstrapPolicy.runtime_operator_provider_model_enablement_requires_execution_request === true,
      requires_promotion: bootstrapPolicy.runtime_operator_provider_model_enablement_requires_promotion === true,
      creates_provider_model_task: bootstrapPolicy.runtime_operator_provider_model_enablement_creates_provider_model_task === true,
      calls_provider_model_now: bootstrapPolicy.runtime_operator_provider_model_enablement_calls_provider_model_now === true,
      production_evidence: bootstrapPolicy.runtime_operator_provider_model_enablement_is_production_evidence === true,
    },
  ];
  const bootstrapModeRows = rows(bootstrapStatus.mode_rows);
  const bootstrapConfigRows = rows(bootstrapStatus.config_rows);
  const bootstrapProviderLinkageRows = rows(bootstrapStatus.provider_linkage_rows);
  const bootstrapActivationReceipt = (bootstrapStatus.live_light_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const bootstrapWarningRows = bootstrapEnvelopeWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const fullPoolStageRows = rows(cache.full_pool_plan_stage_rows);
  const fullPoolFilterRows = rows(cache.full_pool_plan_filter_rows);
  const fullPoolSignalRows = rows(cache.full_pool_required_signal_rows);
  const fullPoolBlockerRows = rows(cache.full_pool_blocker_rows);
  const fullPoolLocalExecutionRows = rows(cache.full_pool_local_execution_rows);
  const deepScanStageRows = rows(cache.deep_scan_stage_rows);
  const deepScanParityRows = rows(cache.deep_scan_parity_rows);
  const deepScanSignalRows = rows(cache.deep_scan_required_signal_rows);
  const deepScanBlockerRows = rows(cache.deep_scan_blocker_rows);
  const deepScanLocalReviewRows = rows(cache.deep_scan_local_review_rows);
  const radarMotionState = [
    String(cache.status ?? "cache_missing"),
    String(cache.scan_mode ?? "no_scan_mode"),
    Number(scanCoverage.missing_signal_group_count ?? 0) ? "coverage_gap" : "coverage_ok",
    Number(counts.provider_blocked_group_count ?? 0) ? "provider_blocked" : "provider_clear",
    Number(counts.result_delta_clarity_visible_gap_count ?? 0) ? "result_delta_gap" : "result_delta_clear",
    Number(counts.degraded_mode_active_count ?? 0) ? "degraded" : "steady"
  ].join(" ");
  const candidateRadarP0Blocked = Boolean(error);
  const ordinaryNextClick = candidateRadarP0Blocked
    ? "先恢复 P0 本地联通"
    : "输入股票代码并点击确认";
  const ordinaryPrimaryActionLabel = candidateRadarP0Blocked
    ? "回一键启动预检恢复联通"
    : "输入代码并确认";
  const ordinaryPrimaryActionBoundary = candidateRadarP0Blocked
    ? "P0 未联通时主下一步只跳转一键启动预检；不创建快扫 task、不调用 provider/model"
    : "主下一步跳到搜票确认区；输入只做本地校验，只有确认按钮创建 Tushare-first POST task";
  const ordinaryOptionalNextClick = Number(counts.candidate_count ?? 0)
    ? "需要更新时再运行本地快扫；搜单票时输入代码后点击生成 3.0 量化推演"
    : "本地快扫和输入股票池保留为可选补证；主路径走搜票确认";
  const candidateRadarRuntimeModeLabel = {
    cache_only: "只读缓存模式",
    manual: "手动任务模式",
    live_light: "轻量实时投研模式",
    live_full: "深度实时投研预留"
  }[String(bootstrapStatus.mode ?? "cache_only")] ?? "未知运行模式";
  const candidateRadarCacheReady = cache.status === "ready";
  const candidateRadarCacheGetReadable = !error && Boolean(cache.status);
  const bootstrapRuntimeModeReady =
    bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet";
  const quantProjectionLocalAppReady =
    !error &&
    candidateRadarCacheGetReadable &&
    bootstrapRuntimeModeReady;
  const desktopOneClickStartupSummary =
    (desktopPreflight.one_click_startup_summary as Record<string, unknown> | undefined) ?? {};
  const desktopP0LocalConnectionReceipt =
    (desktopPreflight.p0_local_connection_receipt as Record<string, unknown> | undefined) ?? {};
  const desktopP0CurrentNextActionRows =
    (desktopPreflight.p0_current_next_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const desktopPreflightReady =
    desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" &&
    (desktopPreflight.desktop_launcher_contract as Record<string, unknown> | undefined)?.status === "local_one_click_launcher_ready";
  const desktopP0StabilityReady =
    desktopOneClickStartupSummary.p0_stability_check_before_open === true &&
    desktopP0LocalConnectionReceipt.p0_stability_check_before_open === true;
  const desktopP0LocalLinkReady =
    desktopOneClickStartupSummary.frontend_backend_connection_ready === true &&
    desktopP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready";
  const desktopP0CurrentReadbackReady =
    candidateRadarCacheGetReadable &&
    bootstrapRuntimeModeReady &&
    desktopPreflightReady;
  const desktopP0ConnectionEvidenceReady =
    desktopP0StabilityReady ||
    desktopP0LocalLinkReady ||
    desktopP0CurrentReadbackReady;
  const desktopP0QuickActionReady = desktopP0CurrentNextActionRows.some(
    (row) => row.p1_entry_enabled === true || row.p0_ready_now === true
  );
  const desktopP0RuntimeModeOrHandoffReady = bootstrapRuntimeModeReady || desktopP0QuickActionReady;
  const desktopP0RuntimePacketsReady =
    !error &&
    desktopP0RuntimeModeOrHandoffReady &&
    desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache";
  const desktopP0ContractEvidenceReady =
    desktopP0ConnectionEvidenceReady ||
    desktopOneClickStartupSummary.status === "one_click_frontend_backend_ready" ||
    desktopP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready" ||
    desktopP0QuickActionReady;
  const desktopP0ConnectionEvidenceLabel = desktopP0StabilityReady
    ? "P0 stability dwell 已通过"
    : desktopP0LocalLinkReady
      ? "本机 FastAPI / desktop preflight 已接上；缺少启动前 stability receipt，仅作为 P1 UI 闸门，不作 release evidence"
      : desktopP0CurrentReadbackReady
        ? "本机 cache / bootstrap / desktop preflight 当前可读；stability receipt 后补，不阻断确认按钮"
      : desktopP0RuntimePacketsReady && desktopP0ContractEvidenceReady
        ? "本机 runtime packet 与 P1 快速入口已接上；旧 stability receipt 可后补"
      : "等待 P0 stability check 或本机连接回读";
  const quantProjectionP0Ready =
    quantProjectionLocalAppReady ||
    desktopP0CurrentReadbackReady ||
    (desktopP0ContractEvidenceReady &&
      desktopP0RuntimePacketsReady);
  const quantProjectionConfirmGateReady =
    quantProjectionP0Ready &&
    quantProjectionLocalAppReady;
  const quantProjectionP0ReadbackReady = quantProjectionConfirmGateReady;
  const ordinaryCacheSourceLabel = candidateRadarCacheReady
    ? "本地候选缓存可用"
    : candidateRadarCacheGetReadable
      ? `候选 cache GET 可读：${String(cache.status)}`
      : "等待本地候选 cache GET";
  const ordinaryTushareSourceLabel = bootstrapLiveLight.tushare_on_open === true ? "live_light 已配置；仍需确认按钮触发 Tushare-first task" : "手动触发或关闭";
  const ordinaryDeepSeekSourceLabel =
    bootstrapLiveLight.deepseek_on_open === true ? "待 governed executor；不作为数据源或动作" : "手动触发或关闭";
  const ordinaryProviderGapLabel =
    Number(counts.provider_blocked_group_count ?? 0) > 0 ? "真实数据补证存在缺口" : "未标记真实数据补证缺口";
  const ordinaryPendingSourceLabel = Number(counts.candidate_radar_production_stage_scope_pending_count ?? 0)
    ? `pending：${String(counts.candidate_radar_production_stage_scope_pending_count)}项证据待补；${ordinaryProviderGapLabel}`
    : `pending：当前摘要未标记新增待补；${ordinaryProviderGapLabel}`;
  const ordinaryDegradedSourceLabel = Number(counts.degraded_mode_active_count ?? 0)
    ? `degraded：${String(counts.degraded_mode_active_count)}项降级`
    : "degraded：未标记降级";
  const ordinaryMissingEvidence = [
    Number(counts.candidate_radar_production_stage_scope_pending_count ?? 0)
      ? `退旧雷达前还缺：${String(counts.candidate_radar_production_stage_scope_pending_count)}项`
      : "",
    Number(counts.candidate_radar_durable_evidence_blocker_count ?? 0)
      ? `耐久证据仍有阻断：${String(counts.candidate_radar_durable_evidence_blocker_count)}项`
      : "",
    Number(counts.candidate_radar_promotion_provider_blocker_count ?? 0) ? "真实数据覆盖待补" : "",
    Number(counts.candidate_radar_promotion_worker_blocker_count ?? 0) ? "全池/深研执行待补" : "",
    Number(counts.candidate_browser_qa_review_blocking_count ?? 0) ? "页面验收证据待补" : "",
    productionPromotionReview.production_promotion_complete === true ? "" : "最终替代复核待补"
  ].filter(Boolean).join(" / ") || "本地快扫缓存已有；退旧雷达前证据仍待补";
  const ordinaryRetirementReadinessLabel = (stageKey: unknown) => {
    const labels: Record<string, string> = {
      cache_render_boundary: "cache/render 静默",
      quick_scan_task_pipeline: "按钮门控快扫",
      local_full_pool_execution_receipt: "本地全池收据",
      local_deep_scan_review_receipt: "本地深研审查",
      worker_runtime_round_trip_link: "本地 worker 链路",
      worker_transport_round_trip_smoke: "本地 worker 传输",
      local_worker_full_pool_fallback_receipt: "本地全池 fallback",
      local_worker_deep_scan_fallback_receipt: "本地深研 fallback",
      worker_full_pool_execution: "全池执行证据",
      worker_deep_scan_execution: "深研执行证据",
      provider_parity_acceptance: "真实数据覆盖",
      search_quant_provider_model_acceptance: "搜票数据账本",
      browser_visual_performance_promotion: "浏览器视觉/性能",
      legacy_retirement_review: "旧雷达退场审查",
      production_promotion_review: "最终替代复核"
    };
    return labels[String(stageKey ?? "")] ?? displayText(stageKey, "待补证据");
  };
  const ordinaryRetirementReadinessDoneCount = Number(
    productionStageScopeManifest.direct_evidence_stage_count ??
      counts.candidate_radar_production_stage_scope_direct_evidence_count ??
      0
  );
  const ordinaryRetirementReadinessMissingCount = Number(
    productionStageScopeManifest.pending_stage_count ??
      counts.candidate_radar_production_stage_scope_pending_count ??
      0
  );
  const ordinaryRetirementReadinessTotalCount = Number(
    productionStageScopeManifest.stage_key_count ??
      productionStageScopeManifest.row_count ??
      ordinaryRetirementReadinessDoneCount + ordinaryRetirementReadinessMissingCount
  );
  const ordinaryRetirementReadinessMissingKeys = Array.isArray(productionStageScopeManifest.pending_stage_keys)
    ? (productionStageScopeManifest.pending_stage_keys as unknown[]).map((item) => String(item))
    : [];
  const ordinaryRetirementReadinessMissingLabels = ordinaryRetirementReadinessMissingKeys.map(ordinaryRetirementReadinessLabel);
  const ordinaryRetirementReadinessMainGaps = [
    productionStageScopeManifest.worker_backed_execution_done === true ? "" : "全池/深研执行证据",
    productionStageScopeManifest.provider_backed_acceptance_done === true ? "" : "真实数据覆盖",
    productionStageScopeManifest.browser_visual_delta_qa_done === true && productionStageScopeManifest.browser_performance_trace_done === true
      ? ""
      : "浏览器视觉和性能",
    productionStageScopeManifest.legacy_retirement_ready === true ? "" : "旧雷达退场审查"
  ].filter(Boolean).join(" / ") || "未标记关键阻断";
  const ordinaryRetirementReadinessNextStep = ordinaryRetirementReadinessMissingLabels.length
    ? `先补 ${ordinaryRetirementReadinessMissingLabels.slice(0, 3).join(" / ")}${ordinaryRetirementReadinessMissingLabels.length > 3 ? " ..." : ""}`
    : productionStageScopeManifest.production_radar_replacement_complete === true
      ? "进入最终 LTG 复核"
      : "等待本地阶段清单回放";
  const ordinaryRetirementReadinessStateLabel = productionStageScopeManifest.production_radar_replacement_complete === true
    ? "退旧雷达已标记可复核，仍需最终 LTG 复核"
    : `退旧雷达未就绪：已确认 ${ordinaryRetirementReadinessDoneCount}/${ordinaryRetirementReadinessTotalCount || "--"}；还缺 ${ordinaryRetirementReadinessMissingCount}`;
  const ordinaryRetirementReadinessItems: MetricItem[] = [
    {
      label: "退旧雷达",
      value: ordinaryRetirementReadinessStateLabel,
      tone: productionStageScopeManifest.production_radar_replacement_complete === true ? "good" : "warn"
    },
    {
      label: "缺口进度",
      value: `已确认 ${ordinaryRetirementReadinessDoneCount}/${ordinaryRetirementReadinessTotalCount || "--"}；待补 ${ordinaryRetirementReadinessMissingCount}`,
      tone: ordinaryRetirementReadinessMissingCount ? "warn" : "good"
    },
    { label: "还缺", value: ordinaryRetirementReadinessMainGaps, tone: ordinaryRetirementReadinessMainGaps === "未标记关键阻断" ? "good" : "warn" },
    { label: "下一步", value: ordinaryRetirementReadinessNextStep },
    { label: "别误判", value: "本地收据、dry-run 和浏览器手册都不是最终完成证据", tone: "warn" },
    { label: "研究边界", value: "候选不是买入指令；不交易、不改交易策略", tone: "good" }
  ];
  const ordinaryBrowserQaStatusLabel =
    browserQaReview.local_browser_qa_review_ready === true
      ? "本地 browser QA 审查已 ready"
      : browserQaEvidence.candidate_browser_qa_evidence_ready === true
        ? "本地 browser QA artifact 已通过；待本地审查"
        : browserQaEvidence.local_browser_qa_evidence_found === true
          ? `本地 browser QA artifact 可读；待复核 ${String(browserQaEvidence.review_required_count ?? 0)} 项`
          : "等待本地 browser QA artifact";
  const ordinaryBrowserQaCoverageLabel =
    browserQaEvidence.motion_viewport_coverage_complete === true
      ? "default/reduced motion 视口覆盖完整"
      : `default ${String(browserQaEvidence.default_motion_viewport_count ?? 0)} / reduced ${String(browserQaEvidence.reduced_motion_viewport_count ?? 0)}；覆盖待补`;
  const ordinaryBrowserQaBlockerLabel =
    Number(browserQaReview.blocking_review_count ?? browserQaEvidence.review_required_count ?? 0)
      ? `本地复核仍有 ${String(browserQaReview.blocking_review_count ?? browserQaEvidence.review_required_count)} 项阻断`
      : "本地复核未标记阻断；仍缺 CI/provider/worker 证据";
  const ordinaryBrowserQaItems: MetricItem[] = [
    {
      label: "本地页面 QA",
      value: ordinaryBrowserQaStatusLabel,
      tone: browserQaReview.local_browser_qa_review_ready === true || browserQaEvidence.candidate_browser_qa_evidence_ready === true ? "good" : "warn"
    },
    {
      label: "覆盖",
      value: ordinaryBrowserQaCoverageLabel,
      tone: browserQaEvidence.motion_viewport_coverage_complete === true ? "good" : "warn"
    },
    {
      label: "复核",
      value: ordinaryBrowserQaBlockerLabel,
      tone: Number(browserQaReview.blocking_review_count ?? browserQaEvidence.review_required_count ?? 0) ? "warn" : "good"
    },
    {
      label: "边界",
      value: "普通页只读 candidate_browser_qa_evidence_summary；不打开浏览器、不创建 task、不调用 provider/model",
      tone: "good"
    },
    {
      label: "不能证明",
      value: "不是 durable CI、不是 provider-backed 验收、不是旧雷达退场",
      tone: "warn"
    }
  ];
  const ordinaryBrowserQaReadbackRows = [
    {
      证据层: "local artifact",
      当前状态: displayText(browserQaEvidence.status, "candidate_browser_qa_evidence_missing"),
      速读: ordinaryBrowserQaStatusLabel,
      边界: "只读本地 ignored runner 报告摘要；普通页不运行 browser QA"
    },
    {
      证据层: "motion viewport coverage",
      当前状态: browserQaEvidence.motion_viewport_coverage_complete === true ? "coverage_complete" : "coverage_pending",
      速读: ordinaryBrowserQaCoverageLabel,
      边界: "本地视口证据不是 CI 或 packaged-runtime evidence"
    },
    {
      证据层: "local review",
      当前状态: displayText(browserQaReview.status, "candidate_browser_qa_review_pending"),
      速读: ordinaryBrowserQaBlockerLabel,
      边界: "审查按钮留在 developer audit；普通速读不创建 POST task"
    },
    {
      证据层: "production replacement",
      当前状态: browserQaEvidence.production_radar_replacement_complete === true ? "unexpected_complete" : "not_complete",
      速读: "仍需 full-pool/deep-scan、provider call ledger、durable CI 和 legacy retirement",
      边界: "不能用本地浏览器 artifact 关闭 LTG-13"
    }
  ];
  const ordinaryRetirementReadinessGapRows = productionStageScopeRows
    .filter((row) => row.production_blocker === true || row.direct_evidence_complete !== true)
    .slice(0, 6)
    .map((row) => ({
      缺口项: ordinaryRetirementReadinessLabel(row.stage_key),
      当前状态: displayText(row.current_status),
      缺少证据: Array.isArray(row.missing_evidence)
        ? (row.missing_evidence as unknown[]).map((item) => String(item)).join(" / ")
        : displayText(row.missing_evidence, "等待直接证据"),
      用户下一步: "按全池/深研、真实数据、浏览器验收、旧雷达退场分层补证；不要把本地收据当最终完成",
      边界: "只读本地阶段清单；不创建 task、不调用 Tushare/DeepSeek/GitHub、不交易"
    }));
  const ordinaryBlockedState = Number(counts.degraded_mode_active_count ?? 0)
    ? "有降级状态，见下方明细"
    : Number(counts.replacement_gap_triage_blocking_count ?? 0)
      ? "有替代阻断，见下方明细"
      : "当前缓存未标记阻断或降级";
  const ordinaryLastCache = String(
    cache.loaded_at ?? radarPacket.generated_at ?? radarPacket.updated_at ?? "暂无最近可用缓存"
  );
  const ordinaryRadarResultLocation =
    "结果位置：本页下一票候选池看 Top/Watch/Excluded；搜单票用搜票量化推演；生成后去股票量化推演和次日图谱，只读回放";
  const coarseFineSourceMode = String(coarseFineScreening.source_mode ?? (rows(cache.candidate_rows).length ? "cache_only" : "empty_cache"));
  const coarseFineSourceLabel =
    coarseFineSourceMode === "tushare_backed_sample"
      ? `真实数据样本：${String(coarseFineScreening.provider_api_success_count ?? 0)}/${String(coarseFineScreening.provider_api_call_count ?? 0)} 个接口可回放`
      : coarseFineSourceMode === "local_fallback"
        ? "本地回放：来自已保存的股票池或本地全池记录"
        : coarseFineSourceMode === "cache_only"
          ? "只读本地候选缓存"
          : "暂无候选";
  const coarseFineGapLabel = Number(coarseFineScreening.gap_visible_count ?? 0)
    ? `可见缺口 ${String(coarseFineScreening.gap_visible_count)} 项；先复核来源和缺口`
    : "未标记粗筛/细筛缺口";
  const ordinaryCandidateTopCount = Number(coarseFineScreening.top_count ?? 0) || rows(cache.candidate_rows).length || Number(counts.candidate_count ?? 0);
  const ordinaryCandidateWatchCount = Number(coarseFineScreening.watch_count ?? 0) || rows(radarPacket.watch_candidates).length;
  const ordinaryCandidateExcludedCount = Number(coarseFineScreening.excluded_count ?? 0) || rows(cache.excluded_candidates).length || rows(radarPacket.excluded_candidates).length;
  const ordinaryCandidateGroupLabel =
    `Top ${ordinaryCandidateTopCount} / Watch ${ordinaryCandidateWatchCount} / Excluded ${ordinaryCandidateExcludedCount}`;
  const ordinaryCandidateReviewOrder =
    "先看 Top / Watch / Excluded 分组，再看候选来源、评分说明和缺少证据；不要从 provider 审计表开始";
  const ordinaryCandidateGroupBoundary =
    "Top 是优先复核，Watch 是观察，Excluded 是排除或等待；三者都不是买入、卖出或加仓指令";
  const ordinaryCoarseFineItems: MetricItem[] = [
    { label: "候选分组", value: ordinaryCandidateGroupLabel },
    { label: "数据来源", value: coarseFineSourceLabel, tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn" },
    { label: "cache-only", value: String(coarseFineScreening.cache_only === true || coarseFineSourceMode === "cache_only") },
    { label: "Tushare-backed", value: String(coarseFineScreening.tushare_backed === true), tone: coarseFineScreening.tushare_backed === true ? "good" : "warn" },
    { label: "缺口", value: coarseFineGapLabel, tone: Number(coarseFineScreening.gap_visible_count ?? 0) ? "warn" : "good" },
    { label: "模型解释", value: String(coarseFineScreening.deepseek_status ?? "governed_pending") },
    { label: "边界", value: "候选不是买入指令；不交易、不改交易策略", tone: "good" },
    { label: "LTG-13", value: "候选分组可读；不是最终替代完成", tone: "warn" }
  ];
  const ordinaryCoarseFineGroupRows = topWatchExcludedGroupRows.slice(0, 12).map((row, index) => ({
    序号: displayText(row.display_rank, String(index + 1)),
    分组: displayText(row.group),
    标的: displayText(row.ticker),
    名称: displayText(row.name),
    理由: displayText(row.reason),
    来源: displayText(row.source_mode ?? row.data_source, coarseFineSourceMode),
    缺口: displayText(row.gap_summary, "未标记"),
    边界: "只供复核，不生成买卖动作"
  }));
  const ordinaryCoarseFineStageRows = [...coarseScreeningRows, ...fineScreeningRows].map((row) => ({
    阶段: displayText(row.phase),
    项目: displayText(row.label ?? row.criterion),
    状态: displayText(row.status),
    来源: displayText(row.source_mode, coarseFineSourceMode),
    证据: displayText(row.evidence),
    缺口: row.gap_visible === true ? "有缺口" : "未标记缺口"
  }));
  const ordinaryCandidateReviewRows = rows(cache.candidate_rows).map((row, index) => ({
    序号: displayText(row.rank, String(index + 1)),
    标的: displayText(row.ticker),
    名称: displayText(row.name),
    分数: displayText(row.score),
    复核状态: displayText(row.action_state ?? row.status_label ?? row.tone, "等待复核"),
    证据摘要: displayText(row.evidence_chain_summary, "暂无摘要；查看原始候选详情"),
    来源: displayText(row.source, "本地候选缓存"),
    边界: "按本地缓存顺序复核；不重排、不重算分数、不生成交易动作"
  }));
  const ordinaryScanScopeLabel = [
    `模式：${String(cache.scan_mode ?? "cache_only")}`,
    `范围：${String(scanExecutionSummary.scan_family ?? localPoolAudit.input_source ?? "本地缓存")}`
  ].join(" / ");
  const ordinaryCandidateSourceLabel = [
    String(radarPacket.source ?? localPoolAudit.input_source ?? cache.cache_source ?? "本地缓存"),
    Number(counts.candidate_display_truncated_count ?? 0)
      ? `截断 ${String(counts.candidate_display_truncated_count)} 个候选`
      : "未标记截断"
  ].join(" / ");
  const ordinaryScoringReasonLabel = Number(candidatePriorityExplanation.explained_candidate_count ?? 0)
    ? `按缓存顺序解释 ${String(candidatePriorityExplanation.explained_candidate_count)} 个候选；不重排、不生成交易动作`
    : "按本地缓存顺序展示；评分理由不足会作为缺口显示";
  const candidatePoolLeadCandidateRow = rows(cache.candidate_rows)[0] ?? topWatchExcludedGroupRows[0] ?? {};
  const candidatePoolLeadCandidateTicker = displayText(candidatePoolLeadCandidateRow.ticker ?? candidatePoolLeadCandidateRow["标的"], "暂无首位候选");
  const candidatePoolLeadCandidateName = displayText(candidatePoolLeadCandidateRow.name ?? candidatePoolLeadCandidateRow["名称"], "待补名称");
  const candidatePoolLeadCandidateDisplay = candidatePoolLeadCandidateTicker === "暂无首位候选"
    ? candidatePoolLeadCandidateTicker
    : `${candidatePoolLeadCandidateTicker} ${candidatePoolLeadCandidateName}`;
  const candidatePoolLeadCandidateCanPrefill = normalizeAshareSymbolInput(candidatePoolLeadCandidateTicker).valid;
  const leadCandidatePrefillValidation = normalizeAshareSymbolInput(leadCandidatePrefillSymbol);
  const candidatePoolLeadHandoffPrefillFeedback = leadCandidatePrefillValidation.valid
    ? `已把 ${leadCandidatePrefillValidation.normalized} 带入确认输入框；下一步由你手动点确认，页面不会自动提交。`
    : candidatePoolLeadCandidateCanPrefill
      ? `可把 ${candidatePoolLeadCandidateTicker} 带入确认输入框；带入后仍需你手动确认。`
      : "暂无可带入的首位候选；可以先手动输入股票代码。";
  const prefillLeadCandidateIntoConfirmInput = () => {
    if (!candidatePoolLeadCandidateCanPrefill) return;
    updateSearchSymbolInput(candidatePoolLeadCandidateTicker, "lead_candidate_prefill");
    document.getElementById("candidate-radar-search-quant-projection")?.scrollIntoView({ block: "start" });
  };
  const candidateRadarGroupBriefRow = (keywords: string[]) =>
    topWatchExcludedGroupRows.find((row) => {
      const group = String(row.group ?? row["分组"] ?? "").toLowerCase();
      return keywords.some((keyword) => group.includes(keyword));
    }) ?? {};
  const candidateRadarTopBriefRow = candidateRadarGroupBriefRow(["top", "优先"]);
  const candidateRadarWatchBriefRow = candidateRadarGroupBriefRow(["watch", "观察"]);
  const candidateRadarExcludedBriefRow = candidateRadarGroupBriefRow(["excluded", "exclude", "排除", "等待"]);
  const candidateRadarGroupBriefText = (row: Record<string, unknown>, fallback: string) => {
    const ticker = displayText(row.ticker ?? row["标的"], fallback);
    if (ticker === fallback) return fallback;
    const name = displayText(row.name ?? row["名称"], "");
    const reason = displayText(row.reason ?? row.evidence_chain_summary ?? row["理由"], "理由待补");
    return `${ticker}${name ? ` ${name}` : ""}；${reason}`;
  };
  const candidatePoolFirstScreenItems: MetricItem[] = [
    {
      label: "Top / Watch / Excluded",
      value: ordinaryCandidateGroupLabel,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "来源",
      value: coarseFineSourceLabel,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "缺口",
      value: coarseFineGapLabel,
      tone: Number(coarseFineScreening.gap_visible_count ?? 0) ? "warn" : "good"
    },
    {
      label: "评分理由",
      value: ordinaryScoringReasonLabel,
      tone: Number(candidatePriorityExplanation.explained_candidate_count ?? 0) ? "good" : "warn"
    },
    {
      label: "复核顺序",
      value: "先 Top，再 Watch，最后 Excluded；需要单票解释再点确认输入",
      tone: "good"
    },
    {
      label: "ETF/融资风险",
      value: "涉及 ETF、仓位或融资预算时，转去 ETF / 融资页看风险线；这里不生成加仓或加融资指令",
      tone: "good"
    },
    {
      label: "非买入边界",
      value: ordinaryCandidateGroupBoundary,
      tone: "good"
    }
  ];
  const candidatePoolPlainConclusionStatus = candidateRadarP0Blocked || !candidateRadarCacheGetReadable
    ? "p0_check"
    : ordinaryCandidateTopCount
      ? Number(coarseFineScreening.gap_visible_count ?? 0) || ordinaryBlockedState !== "当前缓存未标记阻断或降级"
        ? "readable_degraded"
        : "ready"
      : "empty_cache";
  const candidatePoolPlainConclusionText = candidatePoolPlainConclusionStatus === "ready"
    ? `候选池可读：${ordinaryCandidateGroupLabel}，先按 Top / Watch / Excluded 复核。`
    : candidatePoolPlainConclusionStatus === "readable_degraded"
      ? `候选池可读但有缺口：${coarseFineGapLabel}；${ordinaryBlockedState}。`
      : candidatePoolPlainConclusionStatus === "empty_cache"
        ? "本地回放已接上，但候选池暂无候选；先看来源和缺口，再回确认输入区解释单票。"
        : "候选雷达本地缓存未接上；先恢复本地 FastAPI / cache。";
  const candidatePoolPlainConclusionMissing = candidatePoolPlainConclusionStatus === "ready"
    ? "未标记候选池首屏缺口"
    : candidatePoolPlainConclusionStatus === "readable_degraded"
      ? `${coarseFineGapLabel}；${ordinaryBlockedState}`
      : candidatePoolPlainConclusionStatus === "empty_cache"
        ? "缺 Top / Watch / Excluded 候选；不是本地连接故障"
        : "缺本地候选 cache";
  const candidatePoolPlainConclusionNext = candidatePoolPlainConclusionStatus === "ready"
    ? "先看 Top，再看 Watch，最后看 Excluded；需要单票解释再确认输入"
    : candidatePoolPlainConclusionStatus === "readable_degraded"
      ? "先复核来源和缺口；不要把候选当买入指令"
      : candidatePoolPlainConclusionStatus === "empty_cache"
        ? "回确认输入区解释单票，或等待下一次按钮门控快扫补候选"
        : "打开本地预检或刷新只读 cache";
  const candidatePoolPlainConclusionTone: MetricItem["tone"] = candidatePoolPlainConclusionStatus === "ready"
    ? "good"
    : candidatePoolPlainConclusionStatus === "p0_check"
      ? "neutral"
      : "warn";
  const candidatePoolCurrentResultSentence = candidatePoolPlainConclusionStatus === "ready"
    ? `当前候选池可继续复核：先看 ${candidatePoolLeadCandidateDisplay}，再按 Top / Watch / Excluded 顺序看来源和缺口。`
    : candidatePoolPlainConclusionStatus === "readable_degraded"
      ? `当前候选池可读但有缺口：先复核 ${candidatePoolLeadCandidateDisplay} 的来源，再决定是否解释单票。`
      : candidatePoolPlainConclusionStatus === "empty_cache"
        ? "当前候选池暂无候选：本地回放已接上，先回确认输入区解释单票，或等待按钮门控快扫补候选。"
        : "当前候选池暂不可读：先恢复本地连接，再看候选来源和缺口。";
  const candidatePoolCurrentResultItems: MetricItem[] = [
    {
      label: "当前候选池",
      value: ordinaryCandidateGroupLabel,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "先看一票",
      value: candidatePoolLeadCandidateDisplay,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "为什么能看",
      value: coarseFineSourceLabel,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "还缺什么",
      value: candidatePoolPlainConclusionMissing,
      tone: candidatePoolPlainConclusionStatus === "ready" ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryCandidateTopCount
        ? "解释单票，或继续看量化推演、次日图谱和 ETF/融资风险"
        : candidatePoolPlainConclusionNext,
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "非买入边界",
      value: "这张卡只帮你挑复核对象；不生成买入、卖出、加仓或融资指令",
      tone: "good"
    }
  ];
  const candidatePoolGroupActionItems: MetricItem[] = [
    {
      label: "Top",
      value: ordinaryCandidateTopCount ? `先解释 ${candidatePoolLeadCandidateDisplay}` : "等待 Top 候选",
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "Watch",
      value: ordinaryCandidateWatchCount ? "只观察触发条件、来源和缺口" : "当前无 Watch，继续看 Top 或输入单票",
      tone: ordinaryCandidateWatchCount ? "good" : "neutral"
    },
    {
      label: "Excluded",
      value: ordinaryCandidateExcludedCount ? "先看排除原因，不当成清仓或低风险信号" : "当前无 Excluded，保留排除边界",
      tone: ordinaryCandidateExcludedCount ? "warn" : "neutral"
    },
    {
      label: "结果回放",
      value: "解释单票后再看 Factor、Next 和 ETF/融资风险",
      tone: "good"
    },
    {
      label: "边界",
      value: "这些入口只切本地页面或锚点；不快扫、不 POST、不交易",
      tone: "good"
    }
  ];
  const candidatePoolLeadCandidateGroup = displayText(candidatePoolLeadCandidateRow.group ?? candidatePoolLeadCandidateRow["分组"], ordinaryCandidateTopCount ? "Top" : "无候选");
  const candidatePoolLeadCandidateScore = displayText(candidatePoolLeadCandidateRow.score ?? candidatePoolLeadCandidateRow["分数"], ordinaryCandidateTopCount ? "未标记分数" : "无分数");
  const candidatePoolLeadCandidateReason = displayText(
    candidatePoolLeadCandidateRow.reason ?? candidatePoolLeadCandidateRow.evidence_chain_summary ?? candidatePoolLeadCandidateRow["理由"],
    ordinaryCandidateTopCount ? "评分理由待补；先看来源和缺口" : "当前本地候选 cache 没有 candidate_rows；先看确认输入或刷新本地回放"
  );
  const candidatePoolLeadCandidateSource = displayText(
    candidatePoolLeadCandidateRow.source_mode ?? candidatePoolLeadCandidateRow.data_source ?? candidatePoolLeadCandidateRow.source ?? candidatePoolLeadCandidateRow["来源"],
    coarseFineSourceLabel
  );
  const candidatePoolLeadCandidateGap = displayText(
    candidatePoolLeadCandidateRow.gap_summary ?? candidatePoolLeadCandidateRow.gap ?? candidatePoolLeadCandidateRow["缺口"],
    candidatePoolPlainConclusionMissing
  );
  const candidatePoolLeadReviewSentence = ordinaryCandidateTopCount && candidatePoolLeadCandidateTicker !== "暂无首位候选"
    ? `首个复核对象：${candidatePoolLeadCandidateDisplay}，分组 ${candidatePoolLeadCandidateGroup}，先看评分理由、来源和缺口；它不是买入指令。`
    : "首个复核对象暂缺：当前本地候选 cache 没有 candidate_rows；先看确认输入、最近结果或等待本地候选缓存。";
  const candidatePoolLeadReviewItems: MetricItem[] = [
    {
      label: "首个候选",
      value: candidatePoolLeadCandidateDisplay,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "分组",
      value: candidatePoolLeadCandidateGroup,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "评分/理由",
      value: `${candidatePoolLeadCandidateScore}；${candidatePoolLeadCandidateReason}`,
      tone: candidatePoolLeadCandidateReason.includes("待补") || candidatePoolLeadCandidateReason.includes("没有") ? "warn" : "good"
    },
    {
      label: "来源",
      value: candidatePoolLeadCandidateSource,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "缺口",
      value: candidatePoolLeadCandidateGap,
      tone: candidatePoolLeadCandidateGap.includes("缺") || candidatePoolLeadCandidateGap.includes("待补") || candidatePoolLeadCandidateGap.includes("阻断") ? "warn" : "good"
    },
    {
      label: "下一步",
      value: ordinaryCandidateTopCount ? "解释单票或继续看量化推演、次日图谱和 ETF/融资风险" : candidatePoolPlainConclusionNext,
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "非买入边界",
      value: "Top/Watch/Excluded 只决定复核顺序；不下单、不改持仓、不改 strategy action",
      tone: "good"
    }
  ];
  const candidatePoolLeadReviewRows = [
    {
      读法: "1. 首位候选",
      当前状态: candidatePoolLeadCandidateDisplay,
      用户下一步: ordinaryCandidateTopCount ? "先读评分理由、来源和缺口，再决定是否解释单票。" : "回确认输入区或等待本地候选 cache 回放。",
      证据: "candidate_rows[0] / top_watch_excluded_group_rows[0]",
      边界: "首位候选只是复核对象，不是买入指令。"
    },
    {
      读法: "2. 评分理由",
      当前状态: `${candidatePoolLeadCandidateScore}；${candidatePoolLeadCandidateReason}`,
      用户下一步: "理由不足时先把它当作缺口，不重排、不重算分数。",
      证据: "score / reason / evidence_chain_summary",
      边界: "React 只读缓存字段；不调用模型、不重新打分。"
    },
    {
      读法: "3. 来源和缺口",
      当前状态: `${candidatePoolLeadCandidateSource}；${candidatePoolLeadCandidateGap}`,
      用户下一步: candidatePoolPlainConclusionNext,
      证据: "source_mode / gap_summary / coarse_fine_screening_contract",
      边界: "缺口只提示待补证据；不会从卡片创建 task 或调用 provider。"
    },
    {
      读法: "4. 复核入口",
      当前状态: ordinaryCandidateGroupBoundary,
      用户下一步: ordinaryCandidateTopCount ? "打开确认输入、量化推演、次日图谱或 ETF/融资风险做只读复核。" : "先确认一只股票或等待候选缓存。",
      证据: "local route anchors only",
      边界: "链接只切换本地页面或锚点；不交易、不改策略。"
    }
  ];
  const candidatePoolLeadHandoffSentence = ordinaryCandidateTopCount && candidatePoolLeadCandidateTicker !== "暂无首位候选"
    ? `要继续研究 ${candidatePoolLeadCandidateTicker}，先把它作为当前标的回到确认输入区；再看 Factor、Next、数据能力和 ETF/融资风险。`
    : "暂无首位候选可交接；先回确认输入区解释单票，或等待按钮门控快扫补候选。";
  const candidatePoolLeadHandoffItems: MetricItem[] = [
    {
      label: "候选代码",
      value: candidatePoolLeadCandidateTicker,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "主动作",
      value: ordinaryCandidateTopCount ? "回确认输入区解释单票" : "先确认一只股票",
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "复核顺序",
      value: "确认输入 -> 量化推演 -> 次日图谱 -> 数据能力 -> ETF/融资风险",
      tone: "good"
    },
    {
      label: "数据缺口",
      value: candidatePoolLeadCandidateGap,
      tone: candidatePoolLeadCandidateGap.includes("缺") || candidatePoolLeadCandidateGap.includes("待补") || candidatePoolLeadCandidateGap.includes("阻断") ? "warn" : "good"
    },
    {
      label: "不会发生",
      value: "只在点击带入时写入本地输入框；不提交、不快扫、不外联、不启动 worker 或交易",
      tone: "good"
    },
    {
      label: "非买入边界",
      value: "首位候选只是下一步复核对象，不是买入、卖出、加仓或融资指令",
      tone: "good"
    }
  ];
  const candidatePoolLeadHandoffRows = [
    {
      步骤: "1. 拿到代码",
      当前状态: candidatePoolLeadCandidateTicker,
      用户下一步: ordinaryCandidateTopCount ? "点击带入确认框，再由用户决定是否点确认。" : "等待候选或手动输入股票代码。",
      边界: "不会自动把首位候选写进输入框；点击带入只改本地输入，不自动提交。"
    },
    {
      步骤: "2. 解释单票",
      当前状态: "确认按钮仍按当前输入/P0 状态判断",
      用户下一步: "只有用户在确认输入区点击确认按钮，才创建按钮门控本地任务。",
      边界: "本卡链接只跳转；不会调用 postCandidateRadar 或 launchQuantProjection。"
    },
    {
      步骤: "3. 看三面结果",
      当前状态: "Factor / Next / 数据能力 / ETF 融资都是本地只读入口",
      用户下一步: "按同一个标的复核来源、图谱、数据缺口和风险预算。",
      边界: "只读已有 cache / packet；不补调 Tushare、DeepSeek、GitHub 或 worker。"
    },
    {
      步骤: "4. 保持研究边界",
      当前状态: "research-only",
      用户下一步: "把候选当研究线索，不当交易动作。",
      边界: "不下单、不连接 broker、不创建 order endpoint、不改 strategy action。"
    }
  ];
  const candidatePoolPlainConclusionItems: MetricItem[] = [
    {
      label: "一句话结论",
      value: candidatePoolPlainConclusionText,
      tone: candidatePoolPlainConclusionTone
    },
    {
      label: "候选状态",
      value: candidatePoolPlainConclusionStatus,
      tone: candidatePoolPlainConclusionTone
    },
    {
      label: "缺口",
      value: candidatePoolPlainConclusionMissing,
      tone: candidatePoolPlainConclusionStatus === "ready" ? "good" : "warn"
    },
    {
      label: "现在做什么",
      value: candidatePoolPlainConclusionNext,
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读本地候选缓存；不创建 task、不调用 provider/model、不交易，候选不是买入指令",
      tone: "good"
    }
  ];
  const ordinaryTaskBoundary =
    "雷达摘要只读展示候选缓存；manual/live_light 补证必须走 POST task / worker，不在 React 渲染中直连 Tushare 或 DeepSeek";
  const candidateRadarP0AutoLinkRows = [
    {
      联通项: "前端 API 自动联通",
      当前状态: error
        ? "本地 FastAPI 未联通；先停在 P0 恢复"
        : candidateRadarCacheReady
          ? "GET candidate radar cache ready"
          : candidateRadarCacheGetReadable
            ? `GET candidate radar cache reachable: ${String(cache.status)}`
          : loading
            ? "正在读取本地 cache"
            : cache.status
              ? `candidate cache 未 ready：${String(cache.status)}`
              : "等待本地 cache",
      证据: `candidates=${API_BASE_CANDIDATE_DISPLAY_URLS.join(" / ") || API_BASE_DISPLAY_URL}`,
      下一步: error || !candidateRadarCacheGetReadable ? "打开一键启动预检或系统健康页，按四段 ready 恢复" : "继续确认 bootstrap runtime-mode packet",
      边界: "前端只尝试本机 FastAPI 候选地址；失败只显示离线保护，不启动服务、不创建 task"
    },
    {
      联通项: "bootstrap runtime-mode",
      当前状态: bootstrapRuntimeModeReady ? "runtime-mode packet 已回读" : "等待 bootstrap status",
      证据: "GET /api/bootstrap/status",
      下一步: bootstrapRuntimeModeReady ? "继续确认一键启动预检 packet" : "先让 bootstrap status 变绿",
      边界: "bootstrap GET 只读展示模式；不调用 provider/model、不写 cache/config"
    },
    {
      联通项: "一键启动预检",
      当前状态: desktopPreflightReady ? "desktop preflight one-click packet 已回读" : "等待 desktop preflight cache",
      证据: "GET /api/desktop/preflight-cache",
      下一步: desktopPreflightReady ? "继续确认 P0 stability check" : "先回一键启动预检恢复四段联通",
      边界: "desktop preflight GET 只读回放一键启动 packet；不启动服务、不创建 task、不外联"
    },
    {
      联通项: "P0 stability check",
      当前状态: desktopP0ConnectionEvidenceLabel,
      证据: "one_click_startup_summary + p0_local_connection_receipt",
      下一步: desktopP0ConnectionEvidenceReady ? "继续确认 candidate cache GET 可读" : "先回一键启动预检恢复四段 ready + P0 stability dwell",
      边界: "stability check 或本机连接回读只作为 P1 UI 闸门证据；不启动服务、不创建 task、不调用 provider/model，也不是 release evidence"
    },
    {
      联通项: "进入 P1 闸门",
      当前状态: quantProjectionP0Ready ? "ready：输入保持静默，确认按钮才创建 task" : "blocked：P0 未联通时不要点击确认",
      证据: `frontend_call_ledger=${cacheEnvelopeLedger.some((row) => row.frontend_backend_auto_link_attempted === true)} / desktop_preflight_ledger=${desktopPreflightEnvelopeLedger.length} / p0_stability=${desktopP0StabilityReady} / p0_local_link=${desktopP0LocalLinkReady} / p0_connection_evidence=${desktopP0ConnectionEvidenceReady}`,
      下一步: quantProjectionP0Ready ? "输入代码后点击确认并生成 3.0 量化推演" : "先恢复 P0，再回到下一票雷达",
      边界: "P0 只证明本地前后端联通；不代表 Tushare、DeepSeek、release 或 14 LTG 完成"
    }
  ];
  const candidateRadarP0HandoffPacketRows = rows(desktopPreflight.p0_to_p1_ordinary_handoff_rows).map((row) => ({
    交接项: displayText(row["步骤"] ?? row.step),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["下一步"] ?? row["用户下一步"] ?? row.next_step),
    入口: displayText(row["入口"] ?? row.entry, displayText(row["用户动作"], "#candidates")),
    证据: displayText(row["P0交接证据"] ?? row["证据"] ?? row.evidence, "desktop preflight p0_to_p1_ordinary_handoff_rows"),
    边界: displayText(row["边界"] ?? row.boundary, "只读交接回放；确认按钮之前不创建 task")
  }));
  const candidateRadarP0HandoffRows = candidateRadarP0HandoffPacketRows.length ? candidateRadarP0HandoffPacketRows : [
    {
      交接项: "1. 当前主入口",
      当前状态: quantProjectionP0Ready ? "ready：进入 P1 搜票确认" : "check：先恢复 P0 本地联通",
      用户下一步: quantProjectionP0Ready
        ? "进入下一票雷达的搜票量化推演卡，输入股票代码；输入保持静默，确认按钮才触发 Tushare-first。"
        : "留在一键启动预检，按 FastAPI / bootstrap status / desktop preflight cache / React/Vite 四段恢复。",
      入口: quantProjectionP0Ready ? "#candidate-radar-search-quant-projection" : "#desktop",
      证据: "fallback from candidateRadarP0AutoLinkRows",
      边界: "只读本地交接提示；页面打开和输入不创建 task，确认按钮才是 P1 工作入口"
    },
    {
      交接项: "2. P1 确认按钮",
      当前状态: quantProjectionP0Ready ? "可进入搜票确认" : "暂不进入 P1",
      用户下一步: "代码通过本地校验后点击确认按钮，确认后生成本地投研结果；DeepSeek 解释随确认任务治理执行或安全降级。",
      入口: "下一票雷达确认按钮",
      证据: "fallback from candidateRadarP0AutoLinkRows",
      边界: "页面打开、搜索输入和本表回读都不外联；只有确认按钮可进入 P1 task / worker"
    }
  ];
  const candidateRadarP0HandoffLabel = displayText(
    candidateRadarP0HandoffRows[0]?.["用户下一步"],
    quantProjectionP0Ready ? "进入下一票雷达搜票确认区" : "先恢复 P0 本地联通"
  );
  const quantProjectionSymbolValidation = normalizeAshareSymbolInput(searchSymbol);
  const quantProjectionSymbolReady = quantProjectionSymbolValidation.valid;
  const quantProjectionPersistedTaskId = String(searchQuantProjectionReceipt.latest_task_id ?? searchQuantProjectionReceipt.task_id ?? cache.task_id ?? "");
  const quantProjectionPersistedTaskStep = String(searchQuantProjectionReceipt.latest_task_current_step ?? searchQuantProjectionReceipt.status ?? "");
  const quantProjectionTaskReceiptPayload = (taskReceipt?.data?.task?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const quantProjectionReceiptCallLedger = rows(searchQuantProjectionReceipt.call_ledger);
  const quantProjectionReceiptRequestParams =
    (quantProjectionReceiptCallLedger[0]?.request_params_safe as Record<string, unknown> | undefined) ?? {};
  const quantProjectionPostConfirmReplayContract =
    (quantProjectionTaskReceiptPayload.ordinary_post_confirm_replay_contract as Record<string, unknown> | undefined) ??
    (quantProjectionReceiptRequestParams.ordinary_post_confirm_replay_contract as Record<string, unknown> | undefined) ??
    {};
  const quantProjectionAcceptedTaskSymbol = String(quantProjectionTaskReceiptPayload.symbol ?? searchQuantProjectionReceipt.symbol ?? "");
  const quantProjectionTaskReceiptInputMismatch =
    quantProjectionSymbolReady &&
    Boolean(taskReceipt?.ok || quantProjectionPersistedTaskId) &&
    Boolean(quantProjectionAcceptedTaskSymbol) &&
    quantProjectionAcceptedTaskSymbol !== quantProjectionSymbolValidation.normalized;
  const quantProjectionInputSessionState = quantProjectionTaskReceiptInputMismatch
    ? `已切换输入：最近结果属于 ${quantProjectionAcceptedTaskSymbol}；最近任务属于 ${quantProjectionAcceptedTaskSymbol}；旧 task 属于 ${quantProjectionAcceptedTaskSymbol}；当前输入 ${quantProjectionSymbolValidation.normalized} 需重新点击确认；页面不会把旧回执归属到新代码；不会取消已创建后台 task、不创建新 task、不调用 Tushare/DeepSeek；当前输入 ${quantProjectionSymbolValidation.normalized} 需重新确认。`
    : quantProjectionSymbolReady &&
      Boolean(taskReceipt?.ok || quantProjectionPersistedTaskId) &&
      quantProjectionAcceptedTaskSymbol === quantProjectionSymbolValidation.normalized
    ? `当前输入已有历史结果：${quantProjectionAcceptedTaskSymbol}；再次点击确认会重新生成本地结果，旧结果只作为参考。`
    : "修改输入只切换本地输入会话；不会自动确认，也不会自动取数。";
  const quantProjectionHistoricalTaskMatchesInput =
    quantProjectionSymbolReady &&
    Boolean(taskReceipt?.ok || quantProjectionPersistedTaskId) &&
    quantProjectionAcceptedTaskSymbol === quantProjectionSymbolValidation.normalized;
  const quantProjectionCanSubmit = quantProjectionSymbolReady && quantProjectionConfirmGateReady;
  const quantProjectionSubmitDisabled = !quantProjectionCanSubmit || quantProjectionSubmitting;
  const quantProjectionCanLaunch = !quantProjectionSubmitDisabled;
  const quantProjectionConnectionReadyLabel = quantProjectionP0Ready
    ? "本地 FastAPI 已接上：可以输入股票代码；只有确认按钮会启动本地投研数据链。"
    : "本地 FastAPI/cache 尚未接上：先刷新本地回放或回一键启动预检；输入保持静默，确认按钮不可用。";
  const quantProjectionDisabledReason = quantProjectionSubmitting
    ? "正在确认：请等待本地结果开始回写，避免重复点击。"
    : !quantProjectionP0Ready
    ? "按钮不可用原因：本地 FastAPI/cache 还没接上；先刷新本地回放或回一键启动预检。"
    : quantProjectionCanSubmit
    ? quantProjectionHistoricalTaskMatchesInput
      ? `按钮已启用：${quantProjectionSymbolValidation.normalized} 已有历史结果；再次确认会重新生成本地结果。`
      : `按钮已启用：确认后生成 ${quantProjectionSymbolValidation.normalized} 的本地投研结果。`
    : !quantProjectionConfirmGateReady
    ? "按钮不可用原因：本地 FastAPI/cache 或运行模式回放还没接上；先刷新本地回放或回一键启动预检。"
    : searchSymbol.trim()
      ? `按钮不可用原因：${quantProjectionSymbolValidation.reason}；请输入 6 位 A 股代码或 002008.SZ 这类后缀`
      : "按钮不可用原因：先输入股票代码；输入本身不会启动数据链";
  const quantProjectionInputBoundaryLabel = "输入股票代码只做本地校验；不会创建任务，也不会调用 Tushare 或 DeepSeek；页面打开可从本地 cache 预填最近标的。";
  const candidateRadarOperatorInputHelpId = "candidate-radar-operator-symbol-help";
  const candidateRadarOperatorSubmitHelpId = "candidate-radar-operator-confirm-help";
  const quantProjectionSummaryInputHelpId = "candidate-radar-summary-symbol-help";
  const quantProjectionSummarySubmitHelpId = "candidate-radar-summary-confirm-help";
  const quantProjectionFactorInputHelpId = "candidate-radar-factor-symbol-help";
  const quantProjectionFactorSubmitHelpId = "candidate-radar-factor-confirm-help";
  const quantProjectionSubmitButtonLabel = quantProjectionSubmitting
    ? "正在确认；请等待本地结果开始回写"
    : quantProjectionCanSubmit
    ? `确认 ${quantProjectionSymbolValidation.normalized} 并生成本地投研结果`
    : quantProjectionDisabledReason;
  const quantProjectionSubmitAriaLabel = quantProjectionCanSubmit
    ? quantProjectionSubmitButtonLabel
    : quantProjectionDisabledReason;
  const quantProjectionSubmitErrorLabel = quantProjectionSubmitError
    ? `确认任务创建失败：${quantProjectionSubmitError}；未创建可回放 task；确认任务创建失败：未生成 task id；请检查本地后端连接后重试。确认失败：${quantProjectionSubmitError}；未生成可回放结果，请检查本地后端连接后重试。`
    : "";
  const quantProjectionDisplaySymbol = quantProjectionSymbolValidation.normalized || String(searchQuantProjectionReceipt.symbol ?? "");
  const quantProjectionInputValidation = searchQuantProjectionReceipt.symbol_valid === false
    ? `代码格式阻断：${String(searchQuantProjectionReceipt.symbol_status ?? "invalid_symbol")}`
    : searchQuantProjectionReceipt.symbol_valid === true
      ? `代码格式已通过：${String(searchQuantProjectionReceipt.symbol ?? quantProjectionDisplaySymbol)}`
      : searchSymbol.trim()
        ? quantProjectionSymbolValidation.valid
          ? `本地确认代码：${quantProjectionSymbolValidation.normalized}`
          : `本地格式阻断：${quantProjectionSymbolValidation.reason}`
        : "等待输入股票代码";
  const quantProjectionConfirmedSymbol = quantProjectionCanSubmit
    ? `已确认输入：${quantProjectionSymbolValidation.normalized}`
    : "未确认；输入框不会创建任务；输入框不会启动数据链";
  const quantProjectionNextClick = quantProjectionDisplaySymbol
    ? "确认代码后点击生成 3.0 量化推演；结果会从本地回写后展示"
    : "先输入并确认股票代码，按钮启用后再点击生成 3.0 量化推演";
  const quantProjectionSubmitHint = !quantProjectionP0Ready
    ? "本地未联通：先用一键启动预检恢复 FastAPI、bootstrap status、desktop preflight 和候选缓存；本页不会因为输入或渲染自动取数。"
    : quantProjectionSubmitting
      ? "正在提交确认请求；请等待本地结果开始回写，页面不会重复提交。"
      : quantProjectionTaskReceiptInputMismatch
        ? "当前输入与最近结果不一致：请重新确认当前代码，旧结果只作为历史参考。"
        : quantProjectionCanSubmit
          ? quantProjectionHistoricalTaskMatchesInput
            ? "当前代码已有历史结果；再次点击确认会重新生成本地结果，旧结果保留为参考。"
            : "点击确认后启动本地投研数据链；如果本地凭据不可用，页面会显示可恢复提示。"
          : quantProjectionDisplaySymbol
            ? "当前代码已在本地显示；按钮未启用时先看不可用原因，输入本身不会启动数据链。"
            : "先输入股票代码；仅输入不会创建 task，也不会调用 Tushare 或 DeepSeek；仅输入不会启动数据链。";
  const quantProjectionConfirmChainCheckpointLabel =
    String(searchQuantProjectionConfirmChainCheckpoint.ordinary_status ?? "") ||
    String(searchQuantProjectionConfirmChainCheckpoint.status ?? "");
  const quantProjectionConfirmChainState = quantProjectionSubmitError
    ? "确认任务创建失败：未生成 task id；请检查本地后端连接后重试。确认失败：未生成可回放结果；请检查本地后端连接后重试"
    : quantProjectionSubmitting
    ? "正在确认：按钮已暂时禁用；等待本地结果开始回写"
    : quantProjectionTaskReceiptInputMismatch
    ? `已切换输入：最近结果属于 ${quantProjectionAcceptedTaskSymbol}；当前输入 ${quantProjectionSymbolValidation.normalized} 需重新确认`
    : quantProjectionConfirmChainCheckpointLabel
    ? quantProjectionConfirmChainCheckpointLabel
    : taskReceipt?.ok
    ? "确认已接收：先看进度，成功后回放量化推演和次日图谱"
    : quantProjectionCanSubmit
      ? "点击确认会生成本地投研结果；结果成功后再看量化推演和次日图谱"
      : "等待有效股票代码；输入和搜索不会创建后台链";
  const quantProjectionTaskType = String(taskReceipt?.data?.task?.task_type ?? "");
  const quantProjectionTaskVisible = [
    "run_candidate_radar_quant_projection",
    "run_candidate_radar_quant_projection_provider_model_acceptance"
  ].includes(quantProjectionTaskType);
  const quantProjectionValidationReasonLabel =
    quantProjectionSymbolValidation.reason === "empty_symbol"
      ? "先输入股票代码"
      : quantProjectionSymbolValidation.reason === "require_6_digits_or_suffix"
        ? "需要 6 位 A 股代码，或 002008.SZ 这类后缀"
        : quantProjectionSymbolValidation.reason === "unsupported_a_share_prefix"
          ? "暂不支持这个 A 股前缀"
          : ordinaryUserText(quantProjectionSymbolValidation.reason);
  const quantProjectionSummaryGuidance = quantProjectionSymbolReady
    ? quantProjectionP0Ready
      ? `摘要搜票已识别 ${quantProjectionSymbolValidation.normalized}；下一步点击“确认并生成 3.0 量化推演”，只由确认按钮启动本地投研流程；DeepSeek 解释随任务写入安全模型账本或安全降级。`
      : `摘要搜票已识别 ${quantProjectionSymbolValidation.normalized}；确认按钮在等本地联通闸门变绿，输入和页面打开不会创建后台流程。`
    : searchSymbol.trim()
      ? `摘要搜票格式未通过：${quantProjectionValidationReasonLabel}；不会创建后台流程。`
      : "摘要搜票等待输入代码；输入框只做本地校验，不创建后台流程。";
  const quantProjectionProviderApiSuccessCount = Number(
    searchQuantProviderModelAcceptance.provider_api_success_count ??
    searchQuantProjectionSmallDataWriteback.provider_api_success_count ??
    0
  );
  const quantProjectionProviderApiSuccessLabel = Number.isFinite(quantProjectionProviderApiSuccessCount)
    ? String(quantProjectionProviderApiSuccessCount)
    : "0";
  const quantProjectionProviderApiCallCount = Number(
    searchQuantProviderModelAcceptance.provider_api_call_count ??
    searchQuantProjectionSmallDataWriteback.provider_api_call_count ??
    0
  );
  const quantProjectionProviderApiTotalCount =
    Number.isFinite(quantProjectionProviderApiCallCount) && quantProjectionProviderApiCallCount > 0
      ? quantProjectionProviderApiCallCount
      : quantProjectionProviderApiSuccessCount;
  const quantProjectionProviderApiTotalLabel = Number.isFinite(quantProjectionProviderApiTotalCount)
    ? String(quantProjectionProviderApiTotalCount)
    : "0";
  const quantProjectionProviderLedgerReady =
    searchQuantProviderModelAcceptance.tushare_call_ledger_evidence_done === true ||
    searchQuantProjectionReceipt.p1_tushare_first_provider_ledger_ready === true ||
    searchQuantProjectionSmallDataWriteback.source_task_tushare_provider_ledger_ready === true ||
    searchQuantProjectionSmallDataWriteback.provider_call_ledger_replayed_from_source_task === true ||
    searchQuantProjectionSmallDataWriteback.provider_call_ledger_written === true ||
    searchQuantProjectionSmallDataWriteback.ledger_ready === true ||
    quantProjectionProviderApiSuccessCount > 0;
  const quantProjectionDeepSeekSkippedMissingFacts =
    searchQuantProviderModelAcceptance.deepseek_skipped_missing_facts === true ||
    searchQuantResultLineage.deepseek_skipped_missing_facts === true ||
    searchQuantDeepSeekExplanation.status === "skipped_missing_facts" ||
    searchQuantDeepSeekModelLedger.status === "skipped_missing_facts";
  const quantProjectionDeepSeekSkippedByRequest =
    searchQuantProviderModelAcceptance.deepseek_skipped_by_request === true ||
    policy.search_quant_provider_model_acceptance_deepseek_skipped === true;
  const quantProjectionDeepSeekSkipped =
    quantProjectionDeepSeekSkippedByRequest ||
    quantProjectionDeepSeekSkippedMissingFacts;
  const quantProjectionDeepSeekModelLedgerReady =
    searchQuantProviderModelAcceptance.deepseek_model_ledger_evidence_done === true ||
    searchQuantProviderModelAcceptance.deepseek_model_ledger_recorded === true ||
    Boolean(searchQuantDeepSeekModelLedger.input_hash || searchQuantDeepSeekModelLedger.input_summary_hash);
  const quantProjectionDeepSeekOutputReady =
    searchQuantProviderModelAcceptance.deepseek_output_acceptance_done === true ||
    searchQuantDeepSeekExplanation.status === "success";
  const quantProjectionDeepSeekDegraded =
    quantProjectionDeepSeekSkippedMissingFacts ||
    searchQuantProviderModelAcceptance.deepseek_safe_degraded === true ||
    String(searchQuantDeepSeekExplanation.status ?? "").startsWith("degraded");
  const quantProjectionDeepSeekSummary = displayText(
    searchQuantDeepSeekPayload.summary,
    quantProjectionDeepSeekOutputReady
      ? "DeepSeek 解释已写入安全模型账本"
      : quantProjectionDeepSeekDegraded
        ? quantProjectionDeepSeekSkippedMissingFacts
          ? "模型解释已跳过：Tushare 事实缺失，不编造事实"
          : `模型解释已降级：${displayText(searchQuantProviderModelAcceptance.deepseek_safe_failure_mode ?? searchQuantDeepSeekModelLedger.safe_failure_mode, "safe degraded")}`
        : quantProjectionDeepSeekSkippedByRequest
          ? "模型解释未请求；Tushare 结果不受影响"
          : "等待模型解释账本"
  );
  const quantProjectionDeepSeekVisibleStatus = quantProjectionDeepSeekOutputReady
    ? `${quantProjectionDeepSeekSummary}；安全模型账本已写入`
    : quantProjectionDeepSeekSkippedMissingFacts
      ? `${quantProjectionDeepSeekSummary}；页面保留 Tushare 降级原因和 last-good，不让模型补事实`
    : quantProjectionDeepSeekDegraded
      ? `${quantProjectionDeepSeekSummary}；Tushare 数据、Factor light 和本地图谱继续显示`
      : quantProjectionDeepSeekSummary;
  const quantProjectionCacheSourceLabel =
    searchQuantProjectionReceipt.status ? "本地推演记录可用" : cache.status === "ready" ? "候选缓存可用" : "等待本地缓存";
  const quantProjectionProviderSourceLabel = quantProjectionProviderLedgerReady
    ? `Tushare 数据有本地记录：${quantProjectionProviderApiSuccessLabel} 个接口`
    : searchQuantProjectionReceipt.provider_execution_implemented === true ? "Tushare 数据有本地记录" : "待后台补齐 Tushare 数据记录";
  const quantProjectionModelSourceLabel = quantProjectionDeepSeekSkippedMissingFacts
    ? "模型解释已跳过；缺少事实时不编造，结果按降级/last-good 回放"
    : quantProjectionDeepSeekSkippedByRequest
    ? "模型解释未请求；确认按钮可走治理账本或安全降级"
    : quantProjectionDeepSeekOutputReady
      ? "DeepSeek 解释已写入安全模型账本"
      : quantProjectionDeepSeekDegraded
        ? "DeepSeek 已安全降级，Tushare 结果不受影响"
      : quantProjectionDeepSeekModelLedgerReady
        ? "DeepSeek 模型账本有本地记录"
      : searchQuantProjectionReceipt.model_execution_implemented === true ? "DeepSeek 解释有本地记录" : "模型解释待单独治理能力";
  const quantProjectionTaskBoundary =
    "输入不触发外联；点击确认后只经 POST task / worker 后台运行，React 渲染不直连 Tushare 或 DeepSeek。";
  const quantProjectionConfirmRouteRows = [
    {
      链路项: "普通确认按钮",
      当前状态: quantProjectionCanSubmit ? "ready：点击后创建按钮门控 POST task" : quantProjectionDisabledReason,
      用户下一步: quantProjectionCanSubmit ? "点击确认并生成 3.0 量化推演" : "先让输入和 P0 联通闸门通过",
      证据: "POST /api/candidate-radar/quant-projection",
      边界: "只有按钮点击会 POST；页面打开、输入和 GET cache 不创建 task"
    },
    {
      链路项: "Tushare-first",
      当前状态: quantProjectionProviderLedgerReady
        ? `已回放：Tushare ${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}`
        : "点击确认后由后端 task 串联；凭据缺失时只写本地阻断",
      用户下一步: quantProjectionProviderLedgerReady ? "回放量化推演和次日图谱" : "等待 TaskStatusPanel 和 cache 回放",
      证据: "task call_ledger / search_quant_provider_model_acceptance_receipt",
      边界: "Tushare 只允许在 POST task / worker 内执行；React render 不直连 provider"
    },
    {
      链路项: "DeepSeek",
      当前状态: quantProjectionDeepSeekVisibleStatus,
      用户下一步: quantProjectionDeepSeekOutputReady ? "同屏阅读解释边界，再看量化推演和次日图谱" : "先使用 Tushare-first 和本地图谱；模型失败只按降级展示",
      证据: "include_deepseek=true / sanitized explanation / model_ledger",
      边界: "DeepSeek 不作为数据源，不覆盖价格、因子、operation_zones 或 strategy action"
    },
    {
      链路项: "交易隔离",
      当前状态: "research-only：不下单、不改持仓、不改 strategy action",
      用户下一步: "把结果当研究线索，只读回放 cache / ledger / packet",
      证据: "does_not_execute_trades=true / does_not_modify_strategy_action=true",
      边界: "Radar candidate 和量化推演都不是买入、卖出或加仓指令"
    }
  ];
  const quantProjectionProviderModelReplayState = quantProjectionProviderLedgerReady
    ? `本地缓存已回放数据来源记录；${quantProjectionModelSourceLabel}，不改交易策略`
    : "等待确认按钮启动数据链；本地缓存只显示等待状态";
  const quantProjectionSmallDataExplicitReady =
    searchQuantProjectionSmallDataReadbackCheckpoint.ready === true ||
    searchQuantProjectionSmallDataWriteback.small_data_writeback_ready === true;
  const quantProjectionSmallDataPartialLedgerReady =
    !quantProjectionSmallDataExplicitReady && quantProjectionProviderLedgerReady;
  const quantProjectionSmallDataReady = quantProjectionSmallDataExplicitReady;
  const quantProjectionSmallDataRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_readback_rows);
  const quantProjectionSmallDataTargetRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_target_rows);
  const quantProjectionProviderApiRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_provider_api_rows);
  const quantProjectionSmallDataReplayState =
    String(searchQuantProjectionSmallDataReadbackCheckpoint.ordinary_readback_summary ?? "") ||
    String(searchQuantProjectionSmallDataWriteback.ordinary_readback_summary ?? "") ||
    String(searchQuantProjectionSmallDataWriteback.summary_label ?? "") ||
    (quantProjectionSmallDataReady
      ? `cache / ledger / packet 已回放：小数据三面由本地 cache 确认；packet=command_center_3_candidate_radar_cache`
      : quantProjectionSmallDataPartialLedgerReady
        ? `call_ledger 已回放：Tushare ${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel} 个接口；cache / packet 仍等待小数据三面 ready`
      : searchQuantProjectionReceipt.status
        ? `cache / ledger / packet 等待 Tushare-first 回放；本地记录=${String(searchQuantProjectionReceipt.status)}`
        : "cache / ledger / packet 等待确认按钮创建 task");
  const quantProjectionSmallDataStageLabel =
    String(searchQuantProjectionSmallDataReadbackCheckpoint.ordinary_readback_status ?? "") ||
    String(searchQuantProjectionSmallDataWriteback.ordinary_readback_stage_label ?? "") ||
    quantProjectionSmallDataReplayState;
  const quantProjectionSmallDataWritebackSurfaces = Array.isArray(searchQuantProjectionSmallDataReadbackCheckpoint.writeback_surfaces)
    ? String(searchQuantProjectionSmallDataReadbackCheckpoint.writeback_surfaces.join(" / "))
    : Array.isArray(searchQuantProjectionSmallDataWriteback.writeback_surfaces)
    ? String(searchQuantProjectionSmallDataWriteback.ordinary_readback_surfaces_label ?? searchQuantProjectionSmallDataWriteback.writeback_surfaces.join(" / "))
    : "等待写入 cache / call_ledger / packet";
  const quantProjectionSmallDataReadbackContract =
    String(searchQuantProjectionSmallDataWriteback.ordinary_readback_boundary ?? "") ||
    String(searchQuantProjectionSmallDataWriteback.readback_contract ?? "") ||
    "小数据回放只读取本地 cache / ledger / packet；GET cache 和 React render 不补调 provider/model，不生成交易动作。";
  const quantProjectionWritebackSurfaceCount = Number(searchQuantProjectionWritebackCheckpoint.surface_count ?? 3);
  const quantProjectionWritebackReadableSurfaceCount = Number(searchQuantProjectionWritebackCheckpoint.readable_surface_count ?? 0);
  const quantProjectionWritebackCompleteSurfaceCount = Number(searchQuantProjectionWritebackCheckpoint.complete_surface_count ?? 0);
  const quantProjectionWritebackCheckpointLabel = [
    `readable ${quantProjectionWritebackReadableSurfaceCount}/${quantProjectionWritebackSurfaceCount}`,
    `complete ${quantProjectionWritebackCompleteSurfaceCount}/${quantProjectionWritebackSurfaceCount}`,
    String(searchQuantProjectionWritebackCheckpoint.call_ledger_state ?? "waiting_confirm_task")
  ].join(" / ");
  const quantProjectionP2ThreeSurfaceCheckpointLabel =
    String(searchQuantProjectionP2ThreeSurfaceCheckpoint.ordinary_label ?? "") ||
    String(searchQuantProjectionP2ThreeSurfaceCheckpoint.status ?? "") ||
    quantProjectionWritebackCheckpointLabel;
  const quantProjectionSmallDataProvenance =
    String(searchQuantProjectionSmallDataWriteback.ordinary_readback_provenance_summary ?? "") ||
    "当前读回来自 GET cache 的本地 packet；provider 证据只由 POST task call_ledger 证明，React render 不补调 provider/model。";
  const quantProjectionSmallDataNextStep =
    String(searchQuantProjectionSmallDataWriteback.ordinary_readback_next_step ?? "") ||
    String(searchQuantProjectionSmallDataWriteback.next_action ?? "") ||
    "确认任务完成后回放本地 cache / ledger / packet。";
  const quantProjectionProviderCallSource =
    String(searchQuantProjectionSmallDataWriteback.provider_call_source ?? "") ||
    "pending_no_provider_call";
  const quantProjectionTushareDataCardSummary = quantProjectionProviderLedgerReady
    ? `Tushare 数据卡已回放：${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel} 个接口可从本地账本读取。`
    : taskReceipt?.ok || quantProjectionPersistedTaskId
      ? "Tushare 数据卡等待任务回写：先看任务状态，成功后刷新本地 cache。"
      : "Tushare 数据卡等待确认：输入股票代码不会取数，点击确认后才进入本地数据链。";
  const quantProjectionTushareDataCardGap = quantProjectionProviderLedgerReady
    ? quantProjectionSmallDataReady
      ? "cache / call_ledger / packet 三面已进入本地回放。"
      : "已有 call_ledger；cache / packet 仍等待小数据三面 ready。"
    : "缺 Tushare call_ledger；等待确认任务、本地阻断或授权后的后台回写。";
  const quantProjectionTushareDataCardNext = quantProjectionProviderLedgerReady
    ? quantProjectionSmallDataReady
      ? "查看量化推演结果，再看次日图谱。"
      : "继续看任务状态或刷新本地 cache，等 packet 和 cache 回放齐备。"
    : quantProjectionCanSubmit
      ? "点击确认并生成 3.0 量化推演。"
      : "先让本地连接和股票代码校验通过。";
  const quantProjectionTushareDataCardItems: MetricItem[] = [
    {
      label: "Tushare 数据",
      value: quantProjectionTushareDataCardSummary,
      tone: quantProjectionProviderLedgerReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "接口回放",
      value: quantProjectionProviderLedgerReady
        ? `${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}`
        : "等待本地账本",
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "写入三面",
      value: quantProjectionSmallDataStageLabel,
      tone: quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "DeepSeek",
      value: quantProjectionDeepSeekVisibleStatus,
      tone: "good"
    },
    {
      label: "缺口",
      value: quantProjectionTushareDataCardGap,
      tone: quantProjectionProviderLedgerReady && quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "下一步",
      value: quantProjectionTushareDataCardNext,
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读本地 cache / call_ledger / packet；不会从数据卡调用 Tushare/DeepSeek、创建第二个 task 或交易",
      tone: "good"
    }
  ];
  const quantProjectionTushareDataCardRows = quantProjectionProviderApiRows.length
    ? quantProjectionProviderApiRows.slice(0, 6).map((row) => ({
        接口: displayText(row.api ?? row.interface ?? row.name ?? row.provider_api),
        当前状态: displayText(row.ordinary_label ?? row.status ?? row.call_status),
        证据: displayText(row.evidence ?? row.call_ledger_key ?? row.scope_hash_short, quantProjectionProviderCallSource),
        用户下一步: displayText(row.next_action ?? row["用户下一步"], quantProjectionTushareDataCardNext),
        边界: displayText(row.boundary ?? row["边界"], "接口回放只读本地账本；不会补调数据源、模型或交易")
      }))
    : [
        {
          接口: "trade_cal / daily / daily_basic / moneyflow",
          当前状态: quantProjectionProviderLedgerReady
            ? `已看到 Tushare 账本 ${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}`
            : "等待 Tushare 账本或本地阻断回放",
          证据: quantProjectionProviderCallSource,
          用户下一步: quantProjectionTushareDataCardNext,
          边界: "接口明细只读本地 cache；不会补调数据源、模型或交易"
        }
      ];
  const quantProjectionSmallDataActionRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_action_rows).map((row) => ({
    行动: displayText(row["行动"] ?? row.action_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionSmallDataNextStep),
    入口: displayText(row["入口"] ?? row.entry),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionSmallDataReadbackContract)
  }));
  const quantProjectionSmallDataWritebackStatus = quantProjectionSmallDataReady
    ? "小数据写入位置可回放：cache、call_ledger、packet 已有本地读回；普通入口只显示位置和状态。"
    : taskReceipt?.ok || searchQuantProjectionReceipt.latest_task_id || searchQuantProjectionReceipt.task_id || cache.task_id
      ? "小数据写入等待后台完成：先看任务状态，成功后刷新本地 cache 回放 cache、call_ledger、packet。"
      : "小数据写入等待确认按钮：输入或搜索不会写 cache、call_ledger、packet。";
  const quantProjectionSmallDataOrdinaryReadbackRows = quantProjectionSmallDataRows.map((row) => ({
    写入位置: displayText(row.surface),
    当前状态: displayText(row.ordinary_label ?? row.status),
    证据: displayText(row.evidence, quantProjectionSmallDataStageLabel),
    来源: displayText(row.readback_source, "GET /api/candidate-radar/cache"),
    边界: row.readback_external_calls_triggered === false
      ? "GET cache 只读回放；React render 不补调 provider/model"
      : "等待本地 packet 确认只读边界"
  }));
  const quantProjectionSmallDataWritebackRows = quantProjectionSmallDataTargetRows.length
    ? quantProjectionSmallDataTargetRows
    : quantProjectionSmallDataOrdinaryReadbackRows.length
      ? quantProjectionSmallDataOrdinaryReadbackRows
    : [
        {
          写入位置: "cache",
          当前状态: quantProjectionSmallDataReady ? "本地 cache 可回放" : "等待确认任务完成后写入",
          用户看法: quantProjectionSmallDataReady ? quantProjectionSmallDataStageLabel : "刷新页面只读 cache，不会自动补数",
          边界: "GET cache 只读；不会从 React render 补调 provider/model"
        },
        {
          写入位置: "call_ledger",
          当前状态: quantProjectionProviderLedgerReady
            ? `Tushare provider ledger 可回放：${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel} 个接口`
            : "等待 POST task 写 provider ledger 或本地阻断",
          用户看法: "只看是否已有 ledger 或阻断原因；接口级明细下沉到高级状态",
          边界: "call_ledger 只由后台任务产生；普通页面不展示敏感凭据、raw log 或 provider error"
        },
        {
          写入位置: "packet",
          当前状态: searchQuantProjectionReceipt.status
            ? `packet 已有本地记录：${String(searchQuantProjectionReceipt.status)}`
            : "等待 task receipt 写入 packet",
          用户看法: "packet 用来回放 task id、安全步骤、结果位置和下一步",
          边界: "packet 不包含凭据、不生成交易动作、不覆盖 strategy action"
        }
      ];
  const quantProjectionWritebackSurfaceSummaryRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_surface_summary_rows).map((row) => ({
    写入面: displayText(row["写入面"] ?? row.surface),
    当前状态: displayText(row["当前状态"] ?? row.status),
    回放来源: displayText(row["回放来源"] ?? row.readback_source, "GET /api/candidate-radar/cache"),
    下一步: displayText(row["下一步"] ?? row.next_action, quantProjectionSmallDataNextStep),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionSmallDataReadbackContract)
  }));
  const quantProjectionWritebackSurfaceRows = quantProjectionWritebackSurfaceSummaryRows.length
    ? quantProjectionWritebackSurfaceSummaryRows
    : quantProjectionSmallDataWritebackRows;
  const quantProjectionWritebackIntegrityPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_integrity_rows).map((row) => ({
    检查项: displayText(row["检查项"] ?? row.integrity_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    是否齐备: displayText(row["是否齐备"] ?? row.integrity_state),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionSmallDataNextStep),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionSmallDataReadbackContract)
  }));
  const quantProjectionWritebackIntegrityRows = quantProjectionWritebackIntegrityPacketRows.length
    ? quantProjectionWritebackIntegrityPacketRows
    : [
        {
          检查项: "cache 回放",
          当前状态: quantProjectionSmallDataReady || searchQuantProjectionReceipt.status ? "ready：本地 cache 可回放" : "waiting：等待确认按钮写入 cache",
          是否齐备: quantProjectionSmallDataReady || searchQuantProjectionReceipt.status ? "ready" : "waiting_confirm",
          用户下一步: quantProjectionSmallDataNextStep,
          证据: "GET /api/candidate-radar/cache",
          边界: "GET cache 只读回放；不创建 task、不补调 provider/model"
        },
        {
          检查项: "call_ledger 回放",
          当前状态: quantProjectionProviderLedgerReady ? `ready：Tushare ${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}` : "waiting：等待确认任务或本地阻断 ledger",
          是否齐备: quantProjectionProviderLedgerReady ? "ready" : "waiting_confirm",
          用户下一步: quantProjectionProviderLedgerReady ? "回放量化推演和次日图谱" : "先看任务状态；凭据缺失时按阻断提示处理",
          证据: `provider_call_source=${quantProjectionProviderCallSource}`,
          边界: "call_ledger 只由 POST task / worker 产生；React render 不调用 Tushare"
        },
        {
          检查项: "packet 回放",
          当前状态: searchQuantProjectionReceipt.status ? "ready：candidate radar packet 有本地记录" : "waiting：等待 task 写入 packet",
          是否齐备: searchQuantProjectionReceipt.status ? "ready" : "waiting_confirm",
          用户下一步: "按 task id、安全步骤、结果位置继续回放",
          证据: "command_center_3_candidate_radar_cache",
          边界: "packet 不含凭据、raw log 或交易动作；不覆盖 strategy action"
        }
      ];
  const quantProjectionWritebackReceiptPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_receipt_rows).map((row) => ({
    凭证: displayText(row["凭证"] ?? row.receipt_key ?? row.surface),
    当前状态: displayText(row["当前状态"] ?? row.status),
    读回来源: displayText(row["读回来源"] ?? row.readback_source, "GET /api/candidate-radar/cache"),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionSmallDataReadbackContract)
  }));
  const quantProjectionP2WritebackReceiptRows = quantProjectionWritebackReceiptPacketRows.length
    ? quantProjectionWritebackReceiptPacketRows
    : quantProjectionWritebackIntegrityRows.map((row) => ({
        凭证: displayText(row.检查项, "cache / call_ledger / packet 回放凭证"),
        当前状态: displayText(row.当前状态),
        读回来源: "GET /api/candidate-radar/cache",
        证据: displayText(row.证据),
        边界: displayText(row.边界, quantProjectionSmallDataReadbackContract)
      }));
  const quantProjectionWritebackRecoveryRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_writeback_recovery_rows).map((row) => ({
    恢复项: displayText(row["恢复项"] ?? row.recovery_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionSmallDataNextStep),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionSmallDataReadbackContract)
  }));
  const quantProjectionWritebackRecoveryDisplayRows = quantProjectionWritebackRecoveryRows.length
    ? quantProjectionWritebackRecoveryRows
    : [
        {
          恢复项: "当前阻断",
          当前状态: quantProjectionSmallDataReady
            ? "无 P2 阻断：cache、call_ledger、packet 三面已回放。"
            : quantProjectionSmallDataPartialLedgerReady
              ? "部分恢复：call_ledger 已回放，cache / packet 仍等待小数据三面 ready。"
              : "等待确认任务或本地阻断写入；不是页面自动补数。",
          用户下一步: quantProjectionSmallDataReady
            ? "直接回放股票量化推演和次日图谱。"
            : quantProjectionSmallDataPartialLedgerReady
              ? "继续看 TaskStatusPanel 或刷新本地 cache，等 packet 与 cache 回放齐备。"
              : quantProjectionSmallDataNextStep,
          证据: `provider_call_source=${quantProjectionProviderCallSource}`,
          边界: "只解释本地 cache / ledger / packet 状态；不会创建 task、不调用 provider/model。"
        },
        {
          恢复项: "允许动作",
          当前状态: "确认按钮是唯一可创建 Tushare-first 后台链路的普通入口。",
          用户下一步: "需要更新时重新点击确认按钮；输入、GET cache 和回放链接保持静默。",
          证据: "POST /api/candidate-radar/quant-projection",
          边界: "回放行不创建第二个 task，不补调 Tushare/DeepSeek。"
        },
        {
          恢复项: "DeepSeek 状态",
          当前状态: "DeepSeek 解释只读回放或安全降级；P2 阻断恢复不等待模型。",
          用户下一步: "先恢复 Tushare-first / cache / ledger / packet 回放；模型解释失败时只安全降级。",
          证据: "deepseek_governed_explanation_or_safe_degraded",
          边界: "DeepSeek 不是数据源，不能覆盖价格、factor、operation_zones 或 strategy action。"
        }
      ];
  const quantProjectionP2WritebackRailState = [
    quantProjectionSmallDataReady || searchQuantProjectionReceipt.status ? "cache_visible" : "cache_waiting",
    quantProjectionProviderLedgerReady
      ? "call_ledger_visible"
      : taskReceipt?.ok || quantProjectionPersistedTaskId ? "call_ledger_waiting_task" : "call_ledger_waiting_confirm",
    searchQuantProjectionReceipt.status ? "packet_visible" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "packet_waiting_task" : "packet_waiting_confirm",
    "read_only_boundary"
  ].join(" ");
  const quantProjectionP2WritebackRailSteps = [
    {
      label: "cache",
      state: quantProjectionSmallDataReady || searchQuantProjectionReceipt.status ? ("done" as const) : taskReceipt?.ok || quantProjectionPersistedTaskId ? ("active" as const) : ("waiting" as const),
      detail: quantProjectionSmallDataStageLabel
    },
    {
      label: "call_ledger",
      state: quantProjectionProviderLedgerReady ? ("done" as const) : taskReceipt?.ok || quantProjectionPersistedTaskId ? ("active" as const) : ("waiting" as const),
      detail: quantProjectionProviderLedgerReady ? `Tushare ${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}` : "等待 POST task ledger 或本地阻断"
    },
    {
      label: "packet",
      state: searchQuantProjectionReceipt.status ? ("done" as const) : taskReceipt?.ok || quantProjectionPersistedTaskId ? ("active" as const) : ("waiting" as const),
      detail: searchQuantProjectionReceipt.status ? `packet=${String(searchQuantProjectionReceipt.status)}` : "等待 task receipt 写入 packet"
    },
    {
      label: "只读边界",
      state: "done" as const,
      detail: "GET cache / React render 不补调 provider/model"
    }
  ];
  const quantProjectionFactorNextReady =
    searchQuantProviderModelAcceptance.factor_refresh_executed === true ||
    searchQuantProviderModelAcceptance.next_session_refresh_executed === true ||
    searchQuantProviderModelAcceptance.echarts_payload_refreshed === true ||
    searchQuantProjectionReceipt.factor_refresh_executed === true ||
    searchQuantProjectionReceipt.next_session_refresh_executed === true ||
    searchQuantProjectionReceipt.echarts_payload_refreshed === true;
  const quantProjectionInterpretationExplicitReady =
    searchQuantProjectionInterpretation.interpretation_ready === true;
  const quantProjectionInterpretationPartialLedgerReady =
    !quantProjectionInterpretationExplicitReady && quantProjectionProviderLedgerReady;
  const quantProjectionInterpretationReady = quantProjectionInterpretationExplicitReady;
  const quantProjectionResearchMapState = quantProjectionInterpretationReady
    ? quantProjectionFactorNextReady
      ? `量化推演 / Next Session 图谱已有本地回放；${quantProjectionDeepSeekVisibleStatus}；只解释不改交易策略`
      : `Tushare 已回放；量化推演 / Next Session 图谱等待本地 cache 写入；${quantProjectionDeepSeekVisibleStatus}`
    : quantProjectionInterpretationPartialLedgerReady
      ? "call_ledger 已回放；等待小数据三面 ready 后再开放 P3 速读"
    : searchQuantProjectionReceipt.status
      ? "本地搜票记录已生成；等待 Tushare-first 后再联动量化推演 / Next Session 图谱"
      : "等待确认按钮创建搜票任务后联动量化推演 / Next Session 图谱";
  const quantProjectionMapNextStep = quantProjectionFactorNextReady
    ? "查看量化推演结果，再看次日图谱预览；链接只读回放，不额外刷新外部数据或模型"
    : quantProjectionInterpretationReady
      ? "先读 P3 可解释结果速读里的来源和缺口；Factor/Next/ECharts 等待本地 cache 回放"
    : "先点击确认并生成 3.0 量化推演，再回放量化推演 / Next Session 图谱";
  const quantProjectionInterpretationState =
    String(searchQuantProjectionInterpretation.summary_label ?? "") ||
    (quantProjectionInterpretationReady
      ? "可解释结果：小数据三面已回放；等待 Factor/Next/ECharts 本地图谱补齐"
      : quantProjectionInterpretationPartialLedgerReady
        ? "可解释结果等待小数据三面 ready：call_ledger 已回放，但 cache / packet 未齐备"
      : "解释结果等待 Tushare-first 账本");
  const quantProjectionOrdinaryResultSummary =
    String(searchQuantProjectionInterpretation.ordinary_result_summary ?? "") ||
    quantProjectionInterpretationState;
  const quantProjectionInterpretationNext =
    String(searchQuantProjectionInterpretation.next_action ?? "") ||
    "先点击确认并生成 3.0 量化推演；DeepSeek 解释只读运行，可安全降级";
  const quantProjectionOrdinaryResultNext =
    String(searchQuantProjectionInterpretation.ordinary_result_next_step ?? "") ||
    quantProjectionInterpretationNext;
  const quantProjectionOrdinaryResultBoundary =
    String(searchQuantProjectionInterpretation.ordinary_result_boundary ?? "") ||
    "解释只基于本地 cache / ledger / packet；DeepSeek 不作为数据源，不改交易策略。";
  const quantProjectionOrdinaryResultEvidence =
    String(searchQuantProjectionInterpretation.ordinary_result_evidence ?? "") ||
    `证据：等待 Tushare-first 账本；${quantProjectionDeepSeekVisibleStatus}。`;
  const quantProjectionP3OrdinaryReadableSentence = [
    readableSentencePart("结论", quantProjectionOrdinaryResultSummary, ["结论：", "可读结论："]),
    readableSentencePart("下一步", quantProjectionOrdinaryResultNext, ["下一步："]),
    readableSentencePart("证据", quantProjectionOrdinaryResultEvidence, ["证据："]),
    readableSentencePart("边界", quantProjectionOrdinaryResultBoundary, ["边界："])
  ].join(" / ");
  const quantProjectionP3ExplainableResultCheckpointLabel =
    String(searchQuantProjectionP3ExplainableResultCheckpoint.ordinary_label ?? "") ||
    String(searchQuantProjectionP3ExplainableResultCheckpoint.status ?? "") ||
    quantProjectionOrdinaryResultSummary;
  const quantProjectionInterpretationReplay =
    String(searchQuantProjectionInterpretation.result_replay_label ?? "") ||
    "成功后回放本地结果、ledger 和 packet；GET cache 只读展示";
  const quantProjectionOrdinaryResultReadbackRows = rows(
    cache.ordinary_result_readback_rows ?? searchQuantProjectionInterpretation.ordinary_result_readback_rows
  ).map((row) => ({
    回放项: ordinaryResultSurfaceLabel(row.surface),
    当前状态: displayText(row.ordinary_label ?? row.status),
    来源: displayText(row.readback_source, "cache / ledger / packet"),
    边界: displayText(row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionOrdinaryResultQuickReadRows = rows(
    cache.ordinary_result_quick_read_rows ?? searchQuantProjectionInterpretation.ordinary_result_quick_read_rows
  ).map((row) => ({
    结论: displayText(row["结论"] ?? row.quick_read_item),
    当前状态: displayText(row["当前状态"] ?? row.ordinary_label ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionOrdinaryResultNext),
    证据: displayText(row["证据"] ?? row.evidence, quantProjectionOrdinaryResultEvidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionOrdinaryResultDecisionBriefPacketRows = rows(
    cache.ordinary_result_decision_brief_rows ??
    cache.search_quant_projection_result_decision_brief_rows ??
    searchQuantProjectionInterpretation.ordinary_result_decision_brief_rows
  ).map((row) => ({
    读法: displayText(row["读法"] ?? row.brief_key),
    当前状态: displayText(row["当前状态"] ?? row.ordinary_label ?? row.status, quantProjectionOrdinaryResultSummary),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionOrdinaryResultNext),
    证据: displayText(row["证据"] ?? row.evidence, quantProjectionOrdinaryResultEvidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionOrdinaryResultHandoffRows = rows(
    cache.ordinary_result_handoff_rows ?? searchQuantProjectionInterpretation.ordinary_result_handoff_rows
  ).map((row) => ({
    入口: displayText(row["入口"] ?? row.entry ?? row.handoff_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionOrdinaryResultNext),
    来源任务: displayText(row["来源任务"] ?? row.source_task_id, "waiting_confirm_task"),
    证据: displayText(row["证据"] ?? row.evidence, quantProjectionOrdinaryResultEvidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionOrdinaryResultCheckpointPacketRows = rows(
    cache.ordinary_result_checkpoint_rows ?? cache.search_quant_projection_result_checkpoint_rows ?? searchQuantProjectionInterpretation.ordinary_result_checkpoint_rows
  ).map((row) => ({
    检查点: displayText(row["检查点"] ?? row.checkpoint_key),
    当前状态: displayText(row["当前状态"] ?? row.status, quantProjectionOrdinaryResultSummary),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionOrdinaryResultNext),
    证据: displayText(row["证据"] ?? row.evidence, quantProjectionOrdinaryResultEvidence),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionSafeExplanationFields = Array.isArray(searchQuantProjectionResultCheckpoint.safe_explanation_fields)
    ? searchQuantProjectionResultCheckpoint.safe_explanation_fields.map((item) => displayText(item)).join(" / ")
    : "source / gap / next_step / safety_summary";
  const quantProjectionOrdinaryResultCheckpointRows = quantProjectionOrdinaryResultCheckpointPacketRows.length
    ? quantProjectionOrdinaryResultCheckpointPacketRows
    : [
        {
          检查点: "1. 可读结论",
          当前状态: quantProjectionOrdinaryResultSummary,
          用户下一步: quantProjectionOrdinaryResultNext,
          证据: `ordinary_result_readable=${String(searchQuantProjectionResultCheckpoint.ordinary_result_readable ?? false)}`,
          边界: quantProjectionOrdinaryResultBoundary
        },
        {
          检查点: "2. 来源状态",
          当前状态: displayText(searchQuantProjectionResultCheckpoint.data_source_state, quantProjectionInterpretationReplay),
          用户下一步: quantProjectionInterpretationReplay,
          证据: `evidence_source=${displayText(searchQuantProjectionResultCheckpoint.evidence_source, "local_blocker_or_task_status")}`,
          边界: "来源只从本地 cache / ledger / packet 回放；GET cache 和 React render 不补调 provider/model。"
        },
        {
          检查点: "3. 缺口和下一步",
          当前状态: `missing_evidence_count=${String(searchQuantProjectionResultCheckpoint.missing_evidence_count ?? searchQuantProjectionInterpretation.missing_evidence_count ?? 0)}`,
          用户下一步: displayText(searchQuantProjectionInterpretation.next_action, quantProjectionOrdinaryResultNext),
          证据: `next_session_map_state=${displayText(searchQuantProjectionResultCheckpoint.next_session_map_state, "pending_local_cache_refresh")}`,
          边界: "缺口只作为待补证据；不会从检查点创建 task、刷新图谱或调用模型。"
        },
        {
          检查点: "4. 安全边界",
          当前状态: "只解释 source / gap / next_step / safety_summary；DeepSeek 只读解释可安全降级。",
          用户下一步: "把结果当研究线索；没有 model_ledger 时只显示安全降级，P6 前不声明 14 LTG 完成。",
          证据: `safe_explanation_fields=${quantProjectionSafeExplanationFields}`,
          边界: "不真实交易、不改 strategy action、不覆盖价格/持仓/factor/operation_zones。"
        }
      ];
  const quantProjectionOrdinaryResultQuickRows = quantProjectionOrdinaryResultQuickReadRows.length
    ? quantProjectionOrdinaryResultQuickReadRows
    : [
        {
          结论: "现在能读什么",
          当前状态: quantProjectionOrdinaryResultSummary,
          用户下一步: quantProjectionOrdinaryResultNext,
          证据: quantProjectionOrdinaryResultEvidence,
          边界: quantProjectionOrdinaryResultBoundary
        },
        {
          结论: "结果从哪里回放",
          当前状态: quantProjectionInterpretationReplay,
          用户下一步: "只读查看本地 cache / ledger / packet",
          证据: "cache / call_ledger / packet",
          边界: "GET cache 不创建 task，不刷新 provider/model"
        },
        {
          结论: "还缺什么",
          当前状态: "Tushare-first 账本、Factor/Next/ECharts 本地回放或 DeepSeek 解释账本仍按证据状态显示",
          用户下一步: quantProjectionInterpretationNext,
          证据: "local_evidence_gap_summary",
          边界: "缺口不是买卖指令；DeepSeek 只解释不覆盖数据"
        }
      ];
  const quantProjectionP3DecisionBriefRows = quantProjectionOrdinaryResultDecisionBriefPacketRows.length
    ? quantProjectionOrdinaryResultDecisionBriefPacketRows
    : [
        {
          读法: "1. 先看结论",
          当前状态: quantProjectionOrdinaryResultSummary,
          用户下一步: quantProjectionOrdinaryResultNext,
          证据: quantProjectionOrdinaryResultEvidence,
          边界: quantProjectionOrdinaryResultBoundary
        },
        {
          读法: "2. 再看来源",
          当前状态: quantProjectionInterpretationReplay,
          用户下一步: "只读查看本地 cache / ledger / packet",
          证据: "cache / call_ledger / packet",
          边界: "来源只读回放；GET cache 和 React render 不补调 provider/model。"
        },
        {
          读法: "3. 最后定动作",
          当前状态: `missing_evidence_count=${String(searchQuantProjectionResultCheckpoint.missing_evidence_count ?? searchQuantProjectionInterpretation.missing_evidence_count ?? 0)}`,
          用户下一步: quantProjectionInterpretationNext,
          证据: "local_evidence_gap_summary",
          边界: "只作为研究线索；不下单、不改 strategy action，DeepSeek 只解释不覆盖数据。"
        }
      ];
  const quantProjectionModelGovernanceRows = rows(searchQuantProjectionInterpretation.ordinary_model_governance_rows).map((row) => ({
    治理项: displayText(row["治理项"] ?? row.governance_item),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionInterpretationNext),
    证据: displayText(row["证据"] ?? row.evidence, "search_quant_projection_interpretation_summary"),
    边界: displayText(row["边界"] ?? row.boundary, "DeepSeek 只读解释可安全降级；不作为数据源或交易动作")
  }));
  const quantProjectionDeepSeekChecklistRows = rows(searchQuantProjectionInterpretation.ordinary_deepseek_governed_executor_checklist_rows).map((row) => ({
    检查项: displayText(row["检查项"] ?? row.check_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "不创建 task、不调用模型、不覆盖 action")
  }));
  const quantProjectionDeepSeekReadinessRows = rows(searchQuantProjectionInterpretation.ordinary_deepseek_governed_executor_readiness_rows).map((row) => ({
    检查项: displayText(row["检查项"] ?? row.readiness_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    可执行状态: displayText(row["可执行状态"] ?? row.readiness_state),
    允许动作: displayText(row["允许动作"] ?? row.allowed_action, "未来单独按钮门控 POST task；当前只读回放"),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, "先使用 Tushare-first 和本地图谱"),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "不创建 task、不调用模型、不覆盖 action")
  }));
  const quantProjectionDeepSeekContractRows = rows(searchQuantProjectionInterpretation.ordinary_deepseek_governed_executor_contract_rows).map((row) => ({
    合同项: displayText(row["合同项"] ?? row.contract_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    允许动作: displayText(row["允许动作"] ?? row.allowed_action, "未来单独按钮门控 POST task；当前只读回放"),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, "先使用 P1/P2/P3，本轮不调用模型"),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "不创建 task、不调用模型、不覆盖 action")
  }));
  const quantProjectionDeepSeekGovernanceRows = quantProjectionModelGovernanceRows.length
    ? quantProjectionModelGovernanceRows
    : [
        {
          治理项: "执行门控",
          当前状态: quantProjectionModelSourceLabel,
          用户下一步: "先使用 Tushare-first 和本地图谱；DeepSeek 只读解释可安全降级",
          证据: "local_model_governance_policy",
          边界: "GET cache 和 React render 不调用 DeepSeek"
        },
        {
          治理项: "输出范围",
          当前状态: "只解释来源、缺口和下一步",
          用户下一步: "不覆盖价格、持仓、因子、operation_zones 或 strategy action",
          证据: "allowed_fields=source/gap/next_step/safety_summary",
          边界: "DeepSeek 不作为数据源，不生成交易动作"
        },
        {
          治理项: "不阻塞基础图谱",
          当前状态: "Tushare-first 和 P3 结果速读继续只读回放",
          用户下一步: "DeepSeek 作为后续独立补证",
          证据: "cache / call_ledger / packet",
          边界: "pending/skipped 不阻断基础结果入口"
        }
      ];
  const quantProjectionOrdinaryResultRows = quantProjectionOrdinaryResultReadbackRows.length
    ? quantProjectionOrdinaryResultReadbackRows
    : [
        {
          回放项: "数据来源",
          当前状态: quantProjectionProviderModelReplayState,
          来源: "cache / call_ledger / packet",
          边界: "GET cache 只读回放已有账本；不补调 Tushare、DeepSeek 或 worker"
        },
        {
          回放项: "量化推演",
          当前状态: quantProjectionOrdinaryResultSummary,
          来源: "search_quant_projection_interpretation_summary",
          边界: quantProjectionOrdinaryResultBoundary
        },
        {
          回放项: "次日图谱",
          当前状态: quantProjectionInterpretationReplay,
          来源: "Next Session cache / ECharts payload",
          边界: "次日图谱只读回放本地 cache；缺口只作为待补证据，不创建交易动作"
        },
        {
          回放项: "DeepSeek 解释",
          当前状态: quantProjectionDeepSeekVisibleStatus,
          来源: quantProjectionDeepSeekModelLedgerReady ? "sanitized fact summary / model_ledger" : "safe degraded replay",
          边界: "仅解释，不构成交易指令；不覆盖 Tushare 数据、factor、operation_zones 或 strategy action"
        },
        {
          回放项: "安全边界",
          当前状态: "只解释来源、缺口和下一步；不覆盖价格、持仓、因子、operation_zones 或 strategy action",
          来源: "local_safety_policy",
          边界: "候选雷达不是买入指令；真实交易路径隔离"
        }
      ];
  const quantProjectionCrossModuleAlignment =
    (cache.search_quant_projection_cross_module_alignment as Record<string, unknown> | undefined) ??
    (cache.ordinary_cross_module_alignment as Record<string, unknown> | undefined) ??
    (searchQuantProjectionInterpretation.ordinary_cross_module_alignment as Record<string, unknown> | undefined) ??
    {};
  const quantProjectionCrossModuleAlignmentStatus = displayText(
    quantProjectionCrossModuleAlignment.status,
    quantProjectionFactorNextReady ? "aligned" : "pending_current_symbol_refresh"
  );
  const quantProjectionCrossModuleAlignmentSummary = displayText(
    quantProjectionCrossModuleAlignment.summary_label,
    quantProjectionFactorNextReady
      ? "Factor/Next 本地包已可回放；请核对是否属于当前确认股票。"
      : "Factor/Next 本地包等待刷新到当前确认股票。"
  );
  const quantProjectionCrossModuleAlignmentNext = displayText(
    quantProjectionCrossModuleAlignment.next_action,
    quantProjectionMapNextStep
  );
  const quantProjectionCrossModuleAlignmentTone: MetricItem["tone"] =
    quantProjectionCrossModuleAlignmentStatus === "aligned"
      ? "good"
      : quantProjectionCrossModuleAlignmentStatus.includes("mismatch") ||
          quantProjectionCrossModuleAlignmentStatus.includes("pending") ||
          quantProjectionCrossModuleAlignmentStatus.includes("missing")
        ? "warn"
        : "neutral";
  const quantProjectionCrossModuleAlignmentRows = rows(
    cache.search_quant_projection_cross_module_alignment_rows ??
    cache.ordinary_cross_module_alignment_rows ??
    searchQuantProjectionInterpretation.ordinary_cross_module_alignment_rows
  ).map((row) => ({
    模块: displayText(row["模块"] ?? row.module ?? row.alignment_key),
    当前状态: displayText(row["当前状态"] ?? row.status ?? row.alignment_state),
    本次确认: displayText(row["本次确认"] ?? row.confirmed_symbol, quantProjectionDisplaySymbol || "等待确认"),
    本地包标的: displayText(row["本地包标的"] ?? row.local_symbol ?? row.symbol),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionCrossModuleAlignmentNext),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(
      row["边界"] ?? row.boundary,
      "只读本地 packet；不创建 task、不调用 Tushare/DeepSeek/worker、不交易、不改 strategy action"
    )
  }));
  const quantProjectionOrdinaryResultActionRows = rows(searchQuantProjectionInterpretation.ordinary_result_action_rows).map((row) => ({
    行动: displayText(row["行动"] ?? row.action_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionOrdinaryResultNext),
    入口: displayText(row["入口"] ?? row.entry),
    边界: displayText(row["边界"] ?? row.boundary, quantProjectionOrdinaryResultBoundary)
  }));
  const quantProjectionSourceState = [
    `本地缓存：${quantProjectionCacheSourceLabel}`,
    `Tushare 数据：${quantProjectionProviderSourceLabel}`,
    `DeepSeek 解释：${quantProjectionModelSourceLabel}`,
    `运行模式：${candidateRadarRuntimeModeLabel}`
  ].join(" / ");
  const quantProjectionMissingEvidence = [
    quantProjectionProviderLedgerReady || searchQuantProjectionReceipt.ready_for_real_provider_model_projection === true
      ? ""
      : "Tushare-first 数据回放待补",
    searchQuantProjectionReceipt.production_quant_projection_complete === true ? "" : "完整推演结果待补",
    searchQuantProjectionActivation.local_activation_receipt_ready === true ? "" : "本地推演准备记录待补",
    searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true ? "" : "后台补证申请待准备",
    searchQuantProjectionExecutionRequest.local_execution_request_ready === true ? "" : "后台执行准备待补"
  ].filter(Boolean).join(" / ") || "本地推演记录已显示；当前摘要未标记阻断";
  const quantProjectionBlockedState = searchQuantProjectionReceipt.symbol_valid === false
    ? "输入代码未通过本地校验；不会创建真实数据或模型补证"
    : quantProjectionProviderLedgerReady
      ? "Tushare-first 已回放；DeepSeek 解释按安全模型账本回放或安全降级；Factor/Next/完整推演继续补齐"
    : searchQuantProjectionReceipt.ready_for_real_provider_model_projection === true
      ? "可创建按钮门控补证请求；页面显示仍不自动外联"
      : "等待确认按钮启动本地投研数据链；DeepSeek 解释随确认任务治理执行或安全降级";
  const candidateRadarLtg13DataLedgerState = quantProjectionProviderLedgerReady
    ? `真实数据账本已回放：${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel}`
    : searchQuantProjectionExecutionRequest.local_execution_request_ready === true
      ? "授权准备票据已绑定；等待用户明确运行真实数据账本补证"
      : searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true
        ? "补证 scope 已准备；下一步先生成 execution request"
        : searchQuantProjectionReceipt.ready_for_real_provider_model_projection === true
          ? "单票已可进入补证准备；先生成 dry-run / execution request"
          : "先确认一只股票，生成本地结果后再准备真实数据账本补证";
  const candidateRadarLtg13DataLedgerNext = quantProjectionProviderLedgerReady
    ? "回看股票量化推演和次日图谱；最终推广复核仍需 release/legacy 证据"
    : searchQuantProjectionExecutionRequest.local_execution_request_ready === true
      ? "需要用户明确授权后，才能从折叠审计区运行 Tushare-first 真实数据账本补证"
      : searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true
        ? "先生成 execution request，继续不调用 Tushare/DeepSeek"
        : quantProjectionCanSubmit
          ? "先点击确认并生成 3.0 量化推演"
          : "先输入有效股票代码并恢复本地联通";
  const candidateRadarLtg13PromotionState =
    productionPromotionReview.local_review_ready === true
      ? "最终推广本地 review 已可见，但 production 仍 blocked"
      : "最终推广复核等待真实数据账本、durable CI/release 和旧雷达退场证据";
  const candidateRadarLtg13NextDirectEvidenceItems: MetricItem[] = [
    {
      label: "剩余直接证据",
      value: ordinaryRetirementReadinessMissingLabels.length
        ? ordinaryRetirementReadinessMissingLabels.join(" / ")
        : "等待阶段清单回放",
      tone: ordinaryRetirementReadinessMissingCount ? "warn" : "good"
    },
    {
      label: "真实数据账本",
      value: candidateRadarLtg13DataLedgerState,
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "现在能点",
      value: candidateRadarLtg13DataLedgerNext,
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "最终推广",
      value: candidateRadarLtg13PromotionState,
      tone: productionPromotionReview.ready_to_mark_production_radar_replacement_complete === true ? "good" : "warn"
    },
    {
      label: "授权边界",
      value: "首屏只读提示；未明确授权不运行 Tushare、DeepSeek、GitHub 或 worker",
      tone: "good"
    },
    {
      label: "交易隔离",
      value: "候选不是买入指令；不下单、不改 strategy action",
      tone: "good"
    }
  ];
  const candidateRadarLtg13NextDirectEvidenceRows = [
    {
      证据项: "搜票真实数据账本",
      当前状态: candidateRadarLtg13DataLedgerState,
      用户下一步: candidateRadarLtg13DataLedgerNext,
      缺口: quantProjectionProviderLedgerReady ? "已回放；继续最终推广证据" : "需要显式授权的 Tushare-first task call_ledger",
      边界: "首屏只读展示；不从 React render、输入或 GET cache 调用 Tushare/DeepSeek/GitHub"
    },
    {
      证据项: "最终推广复核",
      当前状态: candidateRadarLtg13PromotionState,
      用户下一步: "补齐真实数据账本、durable CI/release、legacy retirement 后再复核",
      缺口: "production promotion 不能从 local receipt 或本地浏览器 artifact 关闭",
      边界: "不把 local review、dry-run、execution request、matrix 或本地 receipt 当 production complete"
    },
    {
      证据项: "交易隔离",
      当前状态: "当前切片保持 research-only",
      用户下一步: "继续把候选当研究线索，不生成买入/卖出/加仓动作",
      缺口: "真实交易仍是单独项目",
      边界: "不连接 broker、不创建 order endpoint、不修改 holdings 或 strategy action"
    }
  ];
  const candidateRadarRealDataPreflightState = quantProjectionProviderLedgerReady
    ? "真实数据账本已有回放；仍要等推广复核、CI/release 和旧雷达退场"
    : searchQuantProjectionExecutionRequest.local_execution_request_ready === true
      ? "真实数据补证未授权：execution request 已准备，按钮仍保持禁用/降级"
      : "真实数据补证未授权：当前只读本地候选 cache、确认状态和缺口提示";
  const candidateRadarRealDataPreflightItems: MetricItem[] = [
    {
      label: "当前状态",
      value: candidateRadarRealDataPreflightState,
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "授权前提",
      value: "需要用户明确授权本轮真实数据补证；未授权就保持 disabled/degraded",
      tone: "warn"
    },
    {
      label: "安全载荷",
      value: "需要 scope hash + safe payload；敏感凭据不进前端、日志、packet 或报告",
      tone: "good"
    },
    {
      label: "必须留痕",
      value: "provider call_ledger、failure-mode evidence、redaction/no-secret 边界",
      tone: "warn"
    },
    {
      label: "现在可做",
      value: "先看候选池、确认单票、回放 Factor / Next / ETF 风险",
      tone: "good"
    },
    {
      label: "不会发生",
      value: "打开页面、输入、GET cache、本地链接不会调用 Tushare/DeepSeek/GitHub/worker",
      tone: "good"
    },
    {
      label: "交易边界",
      value: "候选不是买入指令；不下单、不改交易策略",
      tone: "good"
    }
  ];
  const candidateRadarRealDataPreflightRows = [
    {
      检查项: "1. 明确授权",
      当前状态: quantProjectionProviderLedgerReady ? "已有账本回放；仍需推广复核" : "未授权时禁用/降级",
      用户下一步: "需要真实数据补证时，先明确授权本轮 scope",
      边界: "不从 render、输入、GET cache 或本地链接触发"
    },
    {
      检查项: "2. 绑定 scope",
      当前状态: searchQuantProjectionExecutionRequest.local_execution_request_ready === true ? "execution request 已准备" : "等待确认票和补证准备",
      用户下一步: "绑定 scope hash 与 safe payload 后再进入补证任务",
      边界: "敏感凭据不进前端、日志、packet 或报告"
    },
    {
      检查项: "3. 留痕回放",
      当前状态: quantProjectionProviderLedgerReady ? "call_ledger 已可回放" : "等待 provider call_ledger 与 failure-mode evidence",
      用户下一步: "补齐 payload、call_ledger、failure-mode evidence 和 redaction 记录",
      边界: "不把 receipt、dry-run、execution request 或 matrix 当 production complete"
    },
    {
      检查项: "4. 推广复核",
      当前状态: productionPromotionReview.ready_to_mark_production_radar_replacement_complete === true ? "推广复核可进入最终确认" : "最终推广仍 blocked",
      用户下一步: "等真实数据账本、durable CI/release 和旧雷达退场证据齐后再复核",
      边界: "本地页面只展示状态，不运行 GitHub、worker 或 legacy retirement"
    },
    {
      检查项: "5. 交易隔离",
      当前状态: "research-only",
      用户下一步: "继续把候选当研究线索，必要时换一只票确认",
      边界: "不下单、不连接 broker、不创建 order endpoint、不改 strategy action"
    }
  ];
  const quantProjectionTushareFirstState = quantProjectionProviderLedgerReady
    ? "Tushare-first 当前进度：Tushare 数据有本地记录；下一步看量化推演和次日图谱预览"
    : searchQuantProjectionReceipt.status
      ? "Tushare-first 当前进度：等待 Tushare 数据回放；普通页只看结果状态"
      : "输入代码并确认后生成本地投研结果";
  const quantProjectionDisplayTaskId = taskId || quantProjectionPersistedTaskId;
  const taskIndexLatestTask = taskIndex?.tasks?.[0];
  const taskIndexLatestConfirmedSymbol = String(
    taskIndex?.latest_confirmed_symbol ??
      (taskIndexLatestTask?.payload_safe as Record<string, unknown> | undefined)?.symbol ??
      ""
  );
  const taskIndexLatestConfirmedTaskId = String(
    taskIndex?.latest_confirmed_task_id ??
      taskIndex?.latest_task_id ??
      taskIndexLatestTask?.task_id ??
      ""
  );
  const taskIndexLatestConfirmedStatus = String(
    taskIndex?.latest_confirmed_task_status ??
      taskIndex?.latest_task_status ??
      taskIndexLatestTask?.status ??
      ""
  );
  const taskIndexLatestConfirmedStep = String(
    taskIndex?.latest_confirmed_task_current_step ??
      taskIndexLatestTask?.current_step ??
      ""
  );
  const taskIndexReadbackSafe =
    taskIndex !== null &&
    taskIndex.external_calls_triggered !== true &&
    taskIndex.readback_external_calls_triggered !== true &&
    taskIndex.latest_confirmed_symbol_readback_external_calls_triggered !== true &&
    taskIndex.latest_confirmed_symbol_creates_task_from_readback !== true;
  const quantProjectionProgressWatchTaskId = taskIndexLatestConfirmedTaskId || quantProjectionDisplayTaskId;
  const quantProjectionResultSymbol =
    quantProjectionAcceptedTaskSymbol ||
    String(searchQuantProviderModelAcceptance.symbol ?? "") ||
    taskIndexLatestConfirmedSymbol ||
    quantProjectionDisplaySymbol;
  const quantProjectionProgressWatchSymbol = quantProjectionResultSymbol || taskIndexLatestConfirmedSymbol || quantProjectionDisplaySymbol;
  const quantProjectionProgressWatchStatus =
    taskIndexLatestConfirmedStatus ||
    (quantProjectionDisplayTaskId ? "cache_replay" : "waiting_confirm");
  const quantProjectionProgressWatchStep =
    taskIndexLatestConfirmedStep ||
    quantProjectionPersistedTaskStep ||
    "等待确认按钮后的本地任务状态";
  const quantProjectionProgressWatchStepLower = quantProjectionProgressWatchStep.toLowerCase();
  const quantProjectionProgressWatchLabel = quantProjectionProgressWatchTaskId
    ? `${quantProjectionProgressWatchSymbol || "当前标的"} / ${quantProjectionProgressWatchStatus}`
    : "等待确认后的进度";
  const quantProjectionProgressWatchReadableStatus = quantProjectionProgressWatchStepLower.includes("tushare_first_chain_submitted_deepseek_skipped")
    ? "本地数据链已接收；等待结果回写"
    : quantProjectionProgressWatchStepLower.includes("blocked_missing_tushare") ||
      quantProjectionProgressWatchStepLower.includes("missing_tushare")
      ? "数据凭据不可用；请先恢复本地配置"
      : quantProjectionProgressWatchStepLower.includes("blocked_")
        ? "确认链路被本地安全门阻断；先看 P0 和凭据状态"
        : quantProjectionProgressWatchTaskId
          ? quantProjectionProgressWatchStatus === "success"
            ? "确认完成；可以查看量化推演和次日图谱"
            : "确认已接收；继续等本地进度刷新"
          : "等待确认按钮；输入股票代码本身保持静默";
  const quantProjectionProgressWatchNext = quantProjectionProgressWatchTaskId
    ? quantProjectionProgressWatchStepLower.includes("blocked_") ||
      quantProjectionProgressWatchStepLower.includes("missing_tushare")
      ? "先恢复本地 P0 / 服务端凭据，再由用户手动重新确认"
      : "查看任务目录；成功后回放股票量化推演和次日图谱"
    : "先输入股票代码并点击确认按钮；输入本身保持静默";
  const quantProjectionTaskIndexProgressItems: MetricItem[] = [
    {
      label: "边用边看",
      value: quantProjectionProgressWatchLabel,
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "本地数据链",
      value: quantProjectionProgressWatchReadableStatus,
      tone: quantProjectionProgressWatchStepLower.includes("blocked_") ||
        quantProjectionProgressWatchStepLower.includes("missing_tushare")
        ? "warn"
        : quantProjectionProgressWatchTaskId
          ? "good"
          : "warn"
    },
    {
      label: "处理建议",
      value: quantProjectionProgressWatchNext,
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "最新确认标的",
      value: quantProjectionProgressWatchSymbol || "等待确认股票代码",
      tone: quantProjectionProgressWatchSymbol ? "good" : "neutral"
    },
    {
      label: "最新任务",
      value: quantProjectionProgressWatchTaskId || "等待确认按钮",
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "当前步骤",
      value: quantProjectionProgressWatchStep,
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "只读来源",
      value: "GET /api/tasks + CandidateRadar cache",
      tone: "good"
    },
    {
      label: "安全边界",
      value: taskIndexReadbackSafe ? "任务索引回读未触发外联、未创建 task" : "等待只读边界回放",
      tone: taskIndexReadbackSafe ? "good" : "warn"
    }
  ];
  const quantProjectionP2P3ConnectionReady = quantProjectionSmallDataReady && quantProjectionInterpretationReady;
  const quantProjectionP2P3ConnectionSentence = quantProjectionP2P3ConnectionReady
    ? `${quantProjectionProgressWatchSymbol || quantProjectionDisplaySymbol || "当前标的"} P2/P3 已接通：cache / call_ledger / packet 三面和 P3 可读结果可从同一条本地确认链回放。`
    : `${quantProjectionProgressWatchSymbol || quantProjectionDisplaySymbol || "当前标的"} P2/P3 等待接通：${quantProjectionSmallDataReady ? "P2 三面已回放" : "P2 三面待回放"}；${quantProjectionInterpretationReady ? "P3 可读结果已回放" : "P3 可读结果待回放"}。`;
  const quantProjectionP2P3ConnectionPrimaryHref = quantProjectionP2P3ConnectionReady
    ? "#factor"
    : quantProjectionProgressWatchTaskId
      ? "#tasks"
      : "#candidate-radar-search-quant-projection";
  const quantProjectionP2P3ConnectionPrimaryLabel = quantProjectionP2P3ConnectionReady
    ? "去股票量化推演复核"
    : quantProjectionProgressWatchTaskId
      ? "看任务进度"
      : "确认一只股票";
  const quantProjectionP2P3ConnectionActionBoundary =
    "P2/P3 接通入口只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek、不交易";
  const quantProjectionP2P3ConnectionItems: MetricItem[] = [
    {
      label: "P2 三面",
      value: quantProjectionSmallDataReady
        ? `已回放：${quantProjectionSmallDataWritebackSurfaces}`
        : `等待三面：${quantProjectionWritebackCheckpointLabel}`,
      tone: quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "P3 结果",
      value: quantProjectionInterpretationReady ? quantProjectionOrdinaryResultSummary : quantProjectionResearchMapState,
      tone: quantProjectionInterpretationReady ? "good" : quantProjectionProviderLedgerReady ? "warn" : "neutral"
    },
    {
      label: "同源任务",
      value: quantProjectionProgressWatchTaskId || "等待确认 task",
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "下一步",
      value: quantProjectionP2P3ConnectionReady
        ? "打开股票量化推演和次日图谱复核；不要把结果当买入指令"
        : quantProjectionProgressWatchNext,
      tone: quantProjectionP2P3ConnectionReady ? "good" : "warn"
    },
    {
      label: "主入口",
      value: quantProjectionP2P3ConnectionPrimaryLabel,
      tone: quantProjectionP2P3ConnectionReady ? "good" : quantProjectionProgressWatchTaskId ? "warn" : "neutral"
    },
    {
      label: "边界",
      value: quantProjectionP2P3ConnectionActionBoundary,
      tone: "good"
    }
  ];
  const quantProjectionLastResult = [
    `当前标的：${quantProjectionDisplaySymbol || "--"}`,
    `本地记录：${String(searchQuantProjectionReceipt.status ?? "暂无")}`,
    `后台状态：${quantProjectionDisplayTaskId ? "已有确认进度" : "未确认"}`
  ].join(" / ");
  const quantProjectionTaskReadbackState = quantProjectionPersistedTaskId
    ? `任务回放：${quantProjectionPersistedTaskId} / ${String(searchQuantProjectionReceipt.latest_task_status ?? "cache")} / ${quantProjectionPersistedTaskStep || "等待状态"}`
    : "任务回放：暂无；确认任务完成后写入本地 cache / packet";
  const quantProjectionLatestTaskState = taskReceipt
    ? quantProjectionTaskReceiptInputMismatch
      ? `最近结果属于 ${quantProjectionAcceptedTaskSymbol}；当前输入 ${quantProjectionSymbolValidation.normalized} 需重新确认`
      : `最近确认：${taskReceipt.ok ? "已接收" : "失败"} / ${String(taskReceipt.data?.task?.current_step ?? taskReceipt.error ?? "等待状态轮询")}`
    : quantProjectionPersistedTaskId
      ? `最近确认：本地回放 / ${quantProjectionPersistedTaskStep || "等待状态"}`
      : taskIndexLatestConfirmedTaskId
        ? `最近确认：${taskIndexLatestConfirmedStatus || "本地索引回放"} / ${taskIndexLatestConfirmedStep || "等待状态"}`
      : "最近确认：暂无；点击确认按钮后显示本地进度";
  const quantProjectionLatestUserProgress = taskReceipt
    ? quantProjectionTaskReceiptInputMismatch
      ? `最近结果属于 ${quantProjectionAcceptedTaskSymbol}；当前输入 ${quantProjectionSymbolValidation.normalized} 需重新确认`
      : taskReceipt.ok
        ? "最近确认：已接收；等待本地进度完成"
        : "最近确认：失败；请查看本地进度提示"
    : quantProjectionPersistedTaskId
      ? "最近确认：本地进度已回放；可刷新结果"
      : taskIndexLatestConfirmedTaskId
        ? "最近确认：本地进度已记录；可继续看结果入口"
        : "最近确认：暂无；点击确认按钮后显示本地进度";
  const quantProjectionSourcePlainStatus =
    quantProjectionProviderLedgerReady || quantProjectionSmallDataReady
      ? "本地结果已有数据来源记录；DeepSeek 解释按安全模型账本回放或安全降级"
      : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "等待本地结果写回；外部数据或模型不会自动刷新"
        : "尚未确认；页面只显示本地候选和历史结果";
  const quantProjectionTushareFirstOrdinaryStage = quantProjectionSubmitError
    ? "确认未完成：先恢复本地 FastAPI 后再重新点击确认"
    : quantProjectionProviderLedgerReady
      ? `Tushare-first 当前进度：Tushare 数据有本地记录；${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel} 个接口；继续看 P2/P3 本地结果`
      : quantProjectionSmallDataPartialLedgerReady
        ? "数据来源已出现，但本地结果包未齐；等待回放后再看 P3"
        : taskReceipt?.ok || quantProjectionPersistedTaskId
          ? "确认已接收：等待本地进度完成后刷新回放"
          : quantProjectionCanSubmit
            ? "当前代码可确认：点击一次按钮生成本地投研结果"
            : quantProjectionP0Ready
              ? "等待有效股票代码；输入本身保持静默"
              : "P0 未联通：先用一键启动预检恢复 FastAPI、bootstrap status、desktop preflight、本机连接证据和 candidate cache；先恢复本地 FastAPI、bootstrap status 和 desktop preflight";
  const quantProjectionTushareFirstOrdinaryNextStep = quantProjectionSubmitError
    ? "回到 P0 联通诊断，恢复后重新点击确认按钮"
    : quantProjectionProviderLedgerReady || quantProjectionSmallDataReady
      ? "打开股票量化推演和次日图谱，只读回放本地 cache / ledger / packet"
      : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "看 TaskStatusPanel；success 后点刷新本地回放"
        : quantProjectionCanSubmit
          ? "点击“确认并生成 3.0 量化推演”"
          : "先输入 6 位 A 股代码或带 .SZ/.SH/.BJ 后缀的代码";
  const quantProjectionTushareFirstOrdinaryEvidence = quantProjectionProviderLedgerReady
    ? "数据来源已可读；P2/P3 继续从本地结果回放"
    : taskReceipt?.ok || quantProjectionPersistedTaskId
      ? "本地进度 / 结果缓存"
      : "本地输入校验 + P0 联通状态；尚未确认";
  const quantProjectionTushareFirstOrdinaryReadinessItems: MetricItem[] = [
    {
      label: "当前进度",
      value: quantProjectionTushareFirstOrdinaryStage,
      tone: quantProjectionProviderLedgerReady || quantProjectionSmallDataReady ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "下一步",
      value: quantProjectionTushareFirstOrdinaryNextStep,
      tone: quantProjectionCanSubmit || taskReceipt?.ok || quantProjectionPersistedTaskId || quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "回放依据",
      value: quantProjectionTushareFirstOrdinaryEvidence,
      tone: quantProjectionProviderLedgerReady || taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : "neutral"
    },
    {
      label: "边界",
      value: "页面打开和输入不自动取数；只有确认按钮启动本地数据链；不交易",
      tone: "good"
    }
  ];
  const quantProjectionBackendPostConfirmOneGlanceItems: MetricItem[] =
    searchQuantProjectionPostConfirmOneGlanceItems.map((row) => {
      const rawTone = String(row.tone ?? "neutral");
      const tone = ["good", "warn", "bad", "neutral"].includes(rawTone) ? rawTone as MetricItem["tone"] : "neutral";
      return {
        label: displayText(row.label ?? row["状态项"] ?? row.item_key, "确认后状态"),
        value: displayText(row.value ?? row["当前状态"] ?? row.status),
        tone
      };
    });
  const quantProjectionOrdinaryTaskRailState = [
    quantProjectionCanSubmit || quantProjectionDisplaySymbol ? "input_ready" : "input_waiting",
    quantProjectionTaskReceiptInputMismatch ? "task_receipt_stale_for_input" : quantProjectionSubmitError ? "task_failed" : quantProjectionSubmitting ? "submitting" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "task_visible" : "task_waiting",
    quantProjectionSmallDataReady ? "cache_replay_ready" : "cache_replay_waiting"
  ].join(" ");
  const quantProjectionAcceptedTask = taskReceipt?.data?.task;
  const quantProjectionAcceptedPayload = (quantProjectionAcceptedTask?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const quantProjectionAcceptedTaskId = String(taskReceipt?.data?.task_id ?? quantProjectionAcceptedTask?.task_id ?? quantProjectionPersistedTaskId ?? "");
  const quantProjectionAcceptedTaskStep = String(quantProjectionAcceptedTask?.current_step ?? quantProjectionPersistedTaskStep ?? "");
  const quantProjectionAcceptedTaskStatus = String(quantProjectionAcceptedTask?.status ?? (quantProjectionAcceptedTaskId ? "cache_replay" : "waiting_confirm"));
  const quantProjectionTaskPanelStaleForCurrentInput = quantProjectionSubmitting || quantProjectionTaskReceiptInputMismatch;
  const quantProjectionTaskPanelStaleNotice = quantProjectionSubmitting
    ? "确认任务正在提交：按钮已暂时禁用；正在提交 Tushare-first 后台链；请等待本地 task id，页面不会重复创建第二个 task。正在提交 Tushare-first 后台任务；请等待本地 task id；任务提交中：正在创建 Tushare-first POST task；正在创建当前代码的新 Tushare-first task；旧任务面板暂不显示，避免把旧 task 当成当前输入的回放。"
    : quantProjectionTaskReceiptInputMismatch
      ? `当前输入与最近任务不一致：先重新点击确认创建当前代码的 task，旧回执只作为历史回放。当前输入 ${quantProjectionSymbolValidation.normalized} 与最近任务 ${quantProjectionAcceptedTaskSymbol} 不一致；旧任务面板暂不显示，需重新点击确认。`
      : !taskId && quantProjectionPersistedTaskId
        ? `当前输入已有历史 task 回放；当前代码已有历史回放；再次点击确认会创建新的 Tushare-first 后台链，旧回放保留为参考。再次点击确认会创建新的 Tushare-first POST task，旧回放只作为参考。最近任务 ${quantProjectionPersistedTaskId} 来自本地 cache 回放；TaskStatusPanel 可恢复本地状态轮询，不创建新 task、不补调 Tushare/DeepSeek。`
        : "";
  const quantProjectionTaskPanelVisible =
    (quantProjectionTaskVisible || Boolean(quantProjectionPersistedTaskId)) && !quantProjectionTaskPanelStaleForCurrentInput;
  const quantProjectionTaskPanelTaskId =
    quantProjectionTaskPanelStaleForCurrentInput ? "" : quantProjectionTaskVisible && taskId ? taskId : quantProjectionPersistedTaskId;
  const manualTaskPanelVisible = Boolean(taskId);
  const manualTaskPanelEmptyNotice = "暂无可轮询任务；点击确认按钮或手动任务后才显示 TaskStatusPanel，不把空 task 当成后端错误。";
  const quantProjectionP1ProgressItems: MetricItem[] = [
    {
      label: "输入状态",
      value: quantProjectionInputValidation,
      tone: quantProjectionSymbolReady ? "good" : searchSymbol.trim() ? "warn" : "neutral"
    },
    {
      label: "确认状态",
      value: quantProjectionConfirmChainState,
      tone: taskReceipt?.ok || quantProjectionCanSubmit ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "确认检查点",
      value: String(searchQuantProjectionConfirmChainCheckpoint.status ?? "等待确认按钮"),
      tone: searchQuantProjectionConfirmChainCheckpoint.provider_ledger_ready === true
        ? "good"
        : searchQuantProjectionConfirmChainCheckpoint.confirm_task_written === true ? "warn" : "neutral"
    },
    {
      label: "最近确认",
      value: quantProjectionLatestTaskState,
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "数据链",
      value: quantProjectionTushareFirstState,
      tone: quantProjectionProviderLedgerReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "P2 回放",
      value: quantProjectionSmallDataStageLabel,
      tone: quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "输入不自动取数；确认按钮才启动本地数据链；不交易、不改交易策略",
      tone: "good"
    }
  ];
  const quantProjectionOrdinaryOneGlanceItems: MetricItem[] = [
    {
      label: "当前标的",
      value: quantProjectionDisplaySymbol || "待输入",
      tone: quantProjectionDisplaySymbol ? "good" : "neutral"
    },
    {
      label: "确认进度",
      value: quantProjectionLatestTaskState,
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "本地回放",
      value: quantProjectionSmallDataReady
        ? "P2 三面已回放"
        : taskReceipt?.ok || quantProjectionPersistedTaskId
          ? "确认进行中；等待本地回放"
          : quantProjectionCanSubmit
            ? "可点击确认生成结果"
            : "等待输入或 P0 联通",
      tone: quantProjectionSmallDataReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "结果",
      value: quantProjectionInterpretationReady ? quantProjectionOrdinaryResultSummary : quantProjectionResearchMapState,
      tone: quantProjectionInterpretationReady ? "good" : quantProjectionProviderLedgerReady ? "warn" : "neutral"
    },
    {
      label: "下一步",
      value: quantProjectionTushareFirstOrdinaryNextStep,
      tone: quantProjectionCanSubmit || taskReceipt?.ok || quantProjectionPersistedTaskId || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "结果入口",
      value: quantProjectionSmallDataReady || quantProjectionInterpretationReady
        ? "股票量化推演 / 次日图谱按同一次确认回放"
        : "确认成功后显示量化推演和次日图谱入口",
      tone: quantProjectionSmallDataReady || quantProjectionInterpretationReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读回放；不交易、不改交易策略",
      tone: "good"
    }
  ];
  const quantProjectionFailedSubmitLedgerRows = quantProjectionSubmitError
    ? (taskReceipt?.call_ledger ?? []).filter((row) => row.frontend_backend_auto_link_attempted === true)
    : [];
  const quantProjectionP0SubmitRecoveryRows = quantProjectionFailedSubmitLedgerRows.length
    ? quantProjectionFailedSubmitLedgerRows.map((row) => ({
        恢复步骤: "P0 本地联通恢复",
        当前状态: row.frontend_backend_auto_link_success === true ? "本地 FastAPI 已联通" : "确认请求未连上本地 FastAPI",
        用户下一步: displayText(
          row.frontend_backend_auto_link_next_action,
          "先运行 scripts/check_command_center_3.command 做 check-only 安全自检；需要启动时再双击 stock-MING Command Center 3.command 或运行 scripts/start_command_center_3.command；联通后刷新页面并重新点击确认。"
        ),
        候选地址: Array.isArray(row.attempted_api_bases)
          ? row.attempted_api_bases.map((item) => displayText(item)).join(" / ")
          : API_BASE_CANDIDATE_DISPLAY_URLS.join(" / "),
        "check-only": displayText(row.frontend_backend_check_only_command, "scripts/check_command_center_3.command"),
        启动器: displayText(row.frontend_backend_start_command, "scripts/start_command_center_3.command"),
        边界: displayText(
          row.frontend_backend_check_only_boundary,
          "check-only 不启动 FastAPI/Vite、不创建 task；确认失败提示不自动重试、不调用 Tushare/DeepSeek。"
        )
      }))
    : quantProjectionSubmitError
      ? [
          {
            恢复步骤: "P0 本地联通恢复",
            当前状态: "确认任务未创建；需要先恢复本地后端连接",
            用户下一步: "先打开一键启动预检或运行 check-only 诊断，确认 FastAPI、bootstrap status、desktop preflight 和 candidate cache GET 可读后，再回到本页重新点击确认。",
            候选地址: API_BASE_CANDIDATE_DISPLAY_URLS.join(" / "),
            "check-only": "scripts/check_command_center_3.command",
            启动器: "scripts/start_command_center_3.command",
            边界: "恢复表只读展示本地联通建议；不自动启动服务、不创建 task、不调用 provider/model。"
          }
        ]
      : [];
  const quantProjectionSubmitRecoveryRows = [
    {
      场景: "后端离线或请求失败",
      当前状态: quantProjectionSubmitError ? quantProjectionSubmitErrorLabel : "未触发失败",
      用户下一步: quantProjectionSubmitError ? "先回 P0 一键启动联通恢复，再重新点击一次确认按钮" : "保持当前输入；确认按钮只在有效代码后可用",
      边界: "失败提示不自动重试、不创建第二个 task、不调用 Tushare/DeepSeek"
    },
    {
      场景: "服务端凭据缺失",
      当前状态: quantProjectionProviderLedgerReady ? "Tushare ledger 已回放" : "可能只写本地阻断或等待 provider ledger",
      用户下一步: quantProjectionProviderLedgerReady ? "继续回放量化推演和次日图谱" : "查看 TaskStatusPanel 与 cache 回放中的阻断原因",
      边界: "普通页不显示凭据值；凭据缺失不触发 DeepSeek，也不生成交易动作"
    },
    {
      场景: "任务已接收但结果未回放",
      当前状态: taskReceipt?.ok || quantProjectionPersistedTaskId ? "等待 TaskStatusPanel success 与 cache 刷新" : "等待确认按钮创建 task id",
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId ? "等任务成功后刷新本地 cache，再看 #factor / #next" : "先确认代码并点击按钮",
      边界: "回放链接只读本地 cache / ledger / packet；不会补调 provider/model"
    }
  ];
  const quantProjectionResumeTaskRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_task_readback_rows).map((row) => ({
    回放项: displayText(row.surface),
    当前状态: displayText(row.ordinary_label ?? row.status),
    来源: displayText(row.readback_source, "candidate_radar_cache_packet"),
    边界: displayText(row.boundary, "GET cache 只读回放；TaskStatusPanel 只轮询本地 FastAPI")
  }));
  const quantProjectionOrdinaryTaskRailSteps = [
    {
      label: "输入代码",
      state: quantProjectionCanSubmit || quantProjectionDisplaySymbol ? ("done" as const) : searchSymbol.trim() ? ("blocked" as const) : ("waiting" as const),
      detail: quantProjectionInputValidation
    },
    {
      label: "任务接收",
      state: quantProjectionSubmitError ? ("blocked" as const) : quantProjectionSubmitting ? ("active" as const) : quantProjectionTaskReceiptInputMismatch ? ("waiting" as const) : (taskReceipt?.ok || quantProjectionAcceptedTaskId) ? ("done" as const) : ("waiting" as const),
      detail: quantProjectionLatestTaskState
    },
    {
      label: "任务轮询",
      state: quantProjectionSubmitError ? ("blocked" as const) : quantProjectionSmallDataReady ? ("done" as const) : (taskId || quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId) ? ("active" as const) : ("waiting" as const),
      detail: (taskId || quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId) ? "TaskStatusPanel 只轮询本地 FastAPI" : "等待本地 task id"
    },
    {
      label: "cache 回放",
      state: quantProjectionSmallDataReady ? ("done" as const) : (taskReceipt?.ok || quantProjectionPersistedTaskId) ? ("active" as const) : ("waiting" as const),
      detail: quantProjectionSmallDataStageLabel
    }
  ];
  const quantProjectionPersistedConfirmedTaskReceiptRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_confirmed_task_receipt_rows).map((row) => ({
    回执项: confirmedTaskReceiptLabel(row.receipt_item),
    当前状态: displayText(row.ordinary_label ?? row.status),
    用户看法: displayText(row.readback_source, "cache / packet 回放"),
    边界: displayText(row.boundary, "GET cache 只读回放；不创建任务、不补调数据源或模型")
  }));
  const quantProjectionConfirmedTaskReceiptRows = quantProjectionPersistedConfirmedTaskReceiptRows.length
    ? quantProjectionPersistedConfirmedTaskReceiptRows
    : [
    {
      回执项: "task_id",
      当前状态: quantProjectionAcceptedTaskId || "等待点击确认按钮",
      用户看法: quantProjectionAcceptedTaskId ? "本次确认已有本地任务编号；先看任务状态，再刷新本地缓存回放结果" : "输入代码不会创建任务；点击确认后才会出现 task id",
      边界: "task id 来自按钮门控 POST 或 cache packet 回放；GET cache 不创建任务"
    },
    {
      回执项: "Tushare-first 链路",
      当前状态: quantProjectionAcceptedTaskId
        ? `include_tushare=${String(quantProjectionAcceptedPayload.include_tushare ?? true)} / include_deepseek=${String(quantProjectionAcceptedPayload.include_deepseek ?? false)}`
        : "等待确认；DeepSeek 按按钮任务治理或安全降级",
      用户看法: "确认按钮提交 Tushare-first 后台链；服务端凭据缺失时只写本地阻断",
      边界: "只有 POST task / worker 可调用 Tushare；React render、搜索输入、GET cache 不外联"
    },
    {
      回执项: "安全步骤",
      当前状态: quantProjectionAcceptedTaskStep || "等待本地任务安全步骤",
      用户看法: `任务状态=${quantProjectionAcceptedTaskStatus}；完成后回放 cache / ledger / packet`,
      边界: "只展示 safe current_step；不展示 raw log、敏感凭据或 provider error；只展示安全步骤"
    },
    {
      回执项: "结果去向",
      当前状态: "股票量化推演 / 次日图谱 / 候选池只读回放",
      用户看法: "先看 TaskStatusPanel；成功后刷新 cache，再打开两个回放入口",
      边界: "DeepSeek 只读解释可安全降级；不真实交易、不改 strategy action"
    }
  ];
  const quantProjectionTaskCacheReadbackRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_task_readback_rows).length
    ? rows(searchQuantProjectionSmallDataWriteback.ordinary_task_readback_rows)
    : [
        {
          回放项: "task_id",
          当前状态: quantProjectionPersistedTaskId || "等待确认任务",
          来源: "candidate_radar_cache_packet",
          边界: "GET cache 只读回放 task id，不创建 task、不补调 provider/model"
        },
        {
          回放项: "current_step",
          当前状态: quantProjectionPersistedTaskStep || "等待任务安全步骤",
          来源: "search_quant_projection_receipt",
          边界: "只展示安全步骤；不展示 raw log、敏感凭据或 provider error"
        },
        {
          回放项: "TaskStatusPanel",
          当前状态: (quantProjectionPersistedTaskId || taskId) ? "可轮询本地任务状态" : "等待 task id",
          来源: "local_task_status",
          边界: "轮询本地任务状态，不调用 Tushare/DeepSeek/GitHub、不写交易动作"
        }
      ];
  const quantProjectionResultReplayState =
    "成功后回放本地结果和结果包；本地缓存只读展示";
  const quantProjectionReplayOrder = quantProjectionInterpretationReady
    ? "回放顺序：先看 Tushare ledger，再看股票量化推演和 DeepSeek 解释账本，最后看次日图谱"
    : taskReceipt?.ok
      ? "确认任务已接收：先看 TaskStatusPanel，再通过 GET cache 回放 Tushare ledger、量化推演和次日图谱"
      : "回放顺序：确认生成后先看任务编号，再刷新本地缓存，最后查看量化推演和次日图谱";
  const quantProjectionConfirmReplayStage = quantProjectionSubmitError
    ? "P1 blocked：确认任务未创建；先恢复本地 FastAPI 连接"
    : quantProjectionSmallDataReady
      ? "P2 ready：cache / ledger / packet 已进入本地回放"
      : taskReceipt?.ok || quantProjectionPersistedTaskId
      ? "P1 accepted：任务已接收；等待 TaskStatusPanel success 后刷新 cache"
        : quantProjectionCanSubmit
          ? "P1 ready：点击确认后创建 Tushare-first POST task"
          : "等待有效股票代码；输入不会启动后台流程";
  const quantProjectionPostConfirmWaitLabel = quantProjectionSubmitError
    ? "确认后未创建任务：先恢复本地 FastAPI，再重新点击确认按钮"
    : quantProjectionSmallDataReady || quantProjectionInterpretationReady
      ? "确认后已进入回放：P2 cache / call_ledger / packet 可读；下一步打开 #factor/#next 只读复核"
    : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "确认后等待顺序：先看 task id，再看 TaskStatusPanel，等待 success 后刷新 cache，最后回放 #factor/#next"
        : "确认前准备：输入有效代码后点击确认按钮，才创建 Tushare-first POST task";
  const quantProjectionReplayBoundary =
    "回放入口区分本地模块路由和页内锚点：#factor/#next 切换到量化推演和次日图谱模块，#candidate-pool 留在候选池；不重新创建 task、不调用 Tushare/DeepSeek、不写 cache；链接只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek、不改 strategy action";
  const quantProjectionReplayDestinationState = quantProjectionSubmitError
    ? "结果入口暂停：确认任务未创建；先恢复本地后端连接，再重新点击确认"
    : quantProjectionFactorNextReady
      ? "结果入口可回放：读取本地 cache / ledger / packet，不额外刷新外部数据或模型"
    : quantProjectionInterpretationReady
      ? "P3 可读结论可回放；量化推演 / 次日图谱入口等待本地刷新"
    : quantProjectionInterpretationPartialLedgerReady
      ? "结果入口等待小数据三面：数据来源已回放，本地结果包未齐备"
    : taskReceipt?.ok || quantProjectionPersistedTaskId
      ? "结果入口等待缓存：先看 TaskStatusPanel，任务完成并刷新 cache 后再回放；任务已接收：先等 TaskStatusPanel 完成，再刷新本地缓存查看量化推演和次日图谱"
      : "结果入口待确认：当前只是本地导航；不会创建 task 或刷新 provider/model";
  const quantProjectionReplayDestinationNextStep = quantProjectionSubmitError
    ? "检查一键启动和本地后端连接，再重新点击确认按钮"
    : quantProjectionFactorNextReady
      ? "先回放股票量化推演，再打开次日图谱复核图谱"
      : quantProjectionInterpretationReady
        ? "先读 P3 结果速读里的来源、缺口和边界；等待本地 Factor/Next/ECharts 回放"
      : quantProjectionInterpretationPartialLedgerReady
        ? "继续等待小数据三面 ready；不要把单独数据来源记录当作 P3 结果完成"
      : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "等待本地进度完成，刷新本地回放后再使用两个入口"
        : "输入有效代码并点击确认；不要从链接期待自动补数";
  const quantProjectionReplayDestinationPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_replay_destination_rows);
  const quantProjectionReplayDestinationRows = quantProjectionReplayDestinationPacketRows.length ? quantProjectionReplayDestinationPacketRows : [
    {
      入口: "股票量化推演",
      当前状态: quantProjectionReplayDestinationState,
      下一步: quantProjectionReplayDestinationNextStep,
      边界: "href #factor 是本地量化推演模块路由；只切换模块，不发 POST task、不调 Tushare/DeepSeek"
    },
    {
      入口: "次日图谱",
      当前状态: quantProjectionFactorNextReady
        ? "次日图谱缓存可回放；只展示本地 Next Session / ECharts payload"
        : quantProjectionReplayDestinationState,
      下一步: quantProjectionFactorNextReady ? "打开次日图谱复核本地 operation_zones 来源" : quantProjectionReplayDestinationNextStep,
      边界: "href #next 是本地次日图谱模块路由；只切换模块，不生成交易动作、不覆盖 strategy action"
    },
    {
      入口: "候选池",
      当前状态: "可随时返回候选池复核来源、分组和缺口",
      下一步: "把推演结果当研究线索，不当买入指令",
      边界: "href #candidate-pool 是本页候选池锚点；Radar candidate 不是交易指令；真实交易路径继续隔离"
    }
  ];
  const quantProjectionPostConfirmOneScreenItems: MetricItem[] = [
    {
      label: "确认接收",
      value: quantProjectionLatestTaskState,
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "P1 最短链路",
      value: displayText(searchQuantProjectionP1ShortestPathCheckpoint.ordinary_label, quantProjectionTushareFirstState),
      tone: searchQuantProjectionP1ShortestPathCheckpoint.tushare_first_ledger_ready === true
        ? "good"
        : String(searchQuantProjectionP1ShortestPathCheckpoint.status ?? "").includes("blocked")
          ? "bad"
          : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "当前阶段",
      value: quantProjectionConfirmReplayStage,
      tone: quantProjectionSmallDataReady || taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "P2 三面",
      value: quantProjectionSmallDataStageLabel,
      tone: quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "P3 结论",
      value: quantProjectionOrdinaryResultSummary,
      tone: quantProjectionInterpretationReady ? "good" : "warn"
    },
    {
      label: "结果状态",
      value: displayText(searchQuantResultVersionSummary.ordinary_summary, "等待确认后的结果状态"),
      tone: searchQuantResultVersionSummary.current_result_promoted === true
        ? "good"
        : searchQuantResultVersionSummary.degraded_result_visible === true
          ? "warn"
          : "neutral"
    },
    {
      label: "结果下一步",
      value: displayText(searchQuantResultVersionSummary.ordinary_next_step, quantProjectionReplayDestinationNextStep),
      tone: searchQuantResultVersionSummary.current_result_promoted === true || quantProjectionInterpretationReady ? "good" : "warn"
    },
    {
      label: "下一步入口",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "只读边界",
      value: "只读回放本地确认记录和结果记录；不创建第二个后台流程、不交易、不改交易策略",
      tone: "good"
    }
  ];
  const searchQuantResultCurrentSymbol = displayText(
    searchQuantResultVersionSummary.current_result_symbol ?? searchQuantCurrentResultLineage.symbol,
    ""
  );
  const searchQuantResultTaskSymbol = displayText(
    searchQuantResultVersionSummary.latest_task_symbol ??
      searchQuantCanonicalResultLineage.latest_attempt_symbol ??
      searchQuantResultLineage.symbol ??
      searchQuantProviderModelAcceptance.symbol,
    ""
  );
  const searchQuantResultSymbolLabel =
    searchQuantResultCurrentSymbol && searchQuantResultTaskSymbol && searchQuantResultCurrentSymbol !== searchQuantResultTaskSymbol
      ? `current ${searchQuantResultCurrentSymbol} / task ${searchQuantResultTaskSymbol}`
      : displayText(searchQuantResultTaskSymbol || searchQuantResultCurrentSymbol, "等待同源标的");
  const searchQuantResultScopeLabel = displayText(
    searchQuantResultVersionSummary.canonical_scope_hash_short ??
      searchQuantResultLineage.scope_hash_short ??
      searchQuantResultLineage.scope_hash ??
      searchQuantProviderModelAcceptance.acceptance_scope_hash_short ??
      searchQuantProviderModelAcceptance.acceptance_scope_hash,
    "等待确认范围"
  );
  const searchQuantCanonicalTaskLabel = displayText(
    searchQuantResultVersionSummary.canonical_task_id ??
      searchQuantResultVersionSummary.canonical_result_task_id ??
      searchQuantCanonicalResultLineage.task_id ??
      searchQuantResultLineage.task_id,
    "等待同源 task"
  );
  const searchQuantCanonicalFactsLabel = displayText(
    searchQuantResultVersionSummary.canonical_facts_package_hash ??
      searchQuantCanonicalResultLineage.facts_package_hash ??
      searchQuantResultLineage.facts_package_hash,
    "等待 facts hash"
  );
  const searchQuantCanonicalReady =
    searchQuantResultVersionSummary.canonical_same_task_fact_model_result_version_ready === true ||
    searchQuantCanonicalResultLineage.same_task_fact_model_result_version_ready === true;
  const searchQuantCurrentResultVersion = displayText(
    searchQuantResultVersionSummary.canonical_result_version ??
      searchQuantResultVersionSummary.current_result_version ??
      searchQuantCanonicalResultLineage.result_version ??
      searchQuantCurrentResultLineage.result_version,
    ""
  );
  const searchQuantCurrentResultLabel = searchQuantCurrentResultVersion
    ? `${searchQuantResultCurrentSymbol || "current"} / ${searchQuantCurrentResultVersion}`
    : "成功后才提升 current result";
  const searchQuantLatestTaskResultVersion = displayText(
    searchQuantResultVersionSummary.latest_task_result_version ??
      searchQuantResultLineage.result_version ??
      searchQuantProviderModelAcceptance.result_version,
    ""
  );
  const searchQuantLatestTaskResultLabel = searchQuantLatestTaskResultVersion
    ? `${searchQuantResultTaskSymbol || "task"} / ${searchQuantLatestTaskResultVersion}`
    : "等待确认后的同源结果版本";
  const searchQuantLastGoodResultSymbol = displayText(
    searchQuantResultVersionSummary.last_good_result_symbol ?? searchQuantLastGoodResultLineage.symbol,
    ""
  );
  const searchQuantLastGoodResultVersion = displayText(
    searchQuantResultVersionSummary.last_good_result_version ?? searchQuantLastGoodResultLineage.result_version,
    ""
  );
  const searchQuantLastGoodResultLabel = searchQuantLastGoodResultVersion
    ? `${searchQuantLastGoodResultSymbol || "last-good"} / ${searchQuantLastGoodResultVersion}`
    : "暂无 last-good";
  const searchQuantDegradedResultVisible =
    searchQuantResultVersionSummary.degraded_result_visible === true || Boolean(searchQuantDegradedResultLineage.result_version);
  const searchQuantDegradedResultSymbol = displayText(
    searchQuantResultVersionSummary.degraded_result_symbol ??
      searchQuantDegradedResultLineage.symbol ??
      searchQuantResultVersionSummary.latest_task_symbol,
    ""
  );
  const searchQuantDegradedResultVersion = displayText(
    searchQuantResultVersionSummary.degraded_result_version ?? searchQuantDegradedResultLineage.result_version,
    ""
  );
  const searchQuantDegradedReason = displayText(
    searchQuantResultVersionSummary.degraded_reason ?? searchQuantDegradedResultLineage.freshness_state,
    "degraded，不覆盖当前结果"
  );
  const searchQuantDegradedResultLabel = searchQuantDegradedResultVisible
    ? `${searchQuantDegradedResultSymbol || "本次任务"} / ${searchQuantDegradedResultVersion || "等待版本"}：${searchQuantDegradedReason}；不覆盖 current`
    : displayText(searchQuantResultVersionSummary.status, "未降级");
  const quantProjectionResultLineageItems: MetricItem[] = [
    {
      label: "当前结果版本",
      value: searchQuantCurrentResultLabel,
      tone: searchQuantCurrentResultVersion ? "good" : "warn"
    },
    {
      label: "本次任务版本",
      value: searchQuantLatestTaskResultLabel,
      tone: searchQuantLatestTaskResultVersion ? "good" : "warn"
    },
    {
      label: "last-good",
      value: searchQuantLastGoodResultLabel,
      tone: searchQuantResultVersionSummary.last_good_result_available === true || searchQuantLastGoodResultVersion ? "good" : "warn"
    },
    {
      label: "本次降级",
      value: searchQuantDegradedResultLabel,
      tone: searchQuantDegradedResultVisible ? "warn" : "good"
    },
    {
      label: "同源结果",
      value: searchQuantCanonicalReady
        ? `${searchQuantCanonicalTaskLabel} / ${searchQuantCanonicalFactsLabel} / ${searchQuantCurrentResultVersion || "等待 result_version"}`
        : "等待同一 task + facts package + result_version",
      tone: searchQuantCanonicalReady ? "good" : "warn"
    },
    {
      label: "同源 task",
      value: displayText(
        searchQuantResultVersionSummary.canonical_task_id ??
          searchQuantResultVersionSummary.latest_task_id ??
          searchQuantResultLineage.task_id ??
          searchQuantProviderModelAcceptance.task_id ??
          quantProjectionProgressWatchTaskId,
        "等待确认 task"
      ),
      tone: searchQuantResultVersionSummary.canonical_task_id || searchQuantResultVersionSummary.latest_task_id || searchQuantResultLineage.task_id || searchQuantProviderModelAcceptance.task_id || quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "同源标的",
      value: searchQuantResultSymbolLabel,
      tone: searchQuantResultTaskSymbol || searchQuantResultCurrentSymbol ? "good" : "warn"
    },
    {
      label: "确认范围",
      value: searchQuantResultScopeLabel,
      tone: searchQuantResultScopeLabel === "等待确认范围" ? "warn" : "good"
    },
    {
      label: "事实包",
      value: searchQuantCanonicalFactsLabel !== "等待 facts hash"
        ? searchQuantCanonicalFactsLabel
        : displayText(searchQuantResultLineage.facts_packet_key, "等待 Tushare facts packet"),
      tone: searchQuantResultLineage.facts_package_status === "ready" ? "good" : "warn"
    },
    {
      label: "输入包",
      value: searchQuantResultInputPacketKeys.length ? searchQuantResultInputPacketKeys.join(" / ") : "等待输入包 key",
      tone: searchQuantResultInputPacketKeys.length ? "good" : "warn"
    },
    {
      label: "数据日期",
      value: displayText(searchQuantResultLineage.data_date ?? searchQuantProviderModelAcceptance.data_date, "等待数据日期"),
      tone: searchQuantResultLineage.data_date || searchQuantProviderModelAcceptance.data_date ? "good" : "warn"
    },
    {
      label: "freshness",
      value: displayText(searchQuantResultLineage.freshness_state ?? searchQuantProviderModelAcceptance.freshness_state, "waiting_confirm"),
      tone: searchQuantResultLineage.freshness_state === "fresh_provider" ? "good" : "warn"
    },
    {
      label: "账本关联",
      value: searchQuantResultProviderLedgerLabel,
      tone: searchQuantResultProviderLedgerIds.length ? "good" : "warn"
    },
    {
      label: "模型账本",
      value: displayText(
        searchQuantResultLineage.model_ledger_id ?? searchQuantProviderModelAcceptance.model_ledger_id,
        quantProjectionDeepSeekModelLedgerReady ? "model ledger recorded" : "DeepSeek skipped/degraded"
      ),
      tone: searchQuantResultLineage.model_ledger_id || searchQuantProviderModelAcceptance.model_ledger_id
        ? "good"
        : quantProjectionDeepSeekSkipped || quantProjectionDeepSeekDegraded ? "warn" : "neutral"
    },
    {
      label: "输出包",
      value: searchQuantResultOutputPacketKeys.length ? searchQuantResultOutputPacketKeys.join(" / ") : "等待输出包 key",
      tone: searchQuantResultOutputPacketKeys.length ? "good" : "warn"
    },
    {
      label: "覆盖保护",
      value: searchQuantResultVersionSummary.old_task_can_overwrite_current === false || searchQuantResultLineage.old_task_can_overwrite_current === false
        ? "旧任务不能覆盖当前结果"
        : "等待 symbol + result_version 保护",
      tone: searchQuantResultVersionSummary.old_task_can_overwrite_current === false || searchQuantResultLineage.old_task_can_overwrite_current === false ? "good" : "warn"
    }
  ];
  const candidateRadarOperatorPostConfirmOneGlanceItems: MetricItem[] = [
    {
      label: "确认接收",
      value: quantProjectionLatestTaskState,
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "warn"
    },
    {
      label: "P2/P3",
      value: quantProjectionP2P3ConnectionReady
        ? "P2 三面和 P3 结论可回放"
        : quantProjectionPostConfirmWaitLabel,
      tone: quantProjectionP2P3ConnectionReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "下一步入口",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只读本地结果；不创建第二个后台流程、不交易、不改交易策略",
      tone: "good"
    }
  ];
  const quantProjectionOrdinaryProgressCheckpointAnchor = quantProjectionSubmitError
    ? "#desktop"
    : quantProjectionSmallDataReady || quantProjectionInterpretationReady
      ? "#factor"
      : "#candidate-radar-search-quant-projection";
  const quantProjectionOrdinaryProgressCheckpointLabel = quantProjectionSubmitError
    ? "回 P0 联通恢复"
    : quantProjectionSmallDataReady || quantProjectionInterpretationReady
      ? "查看结果回放"
      : quantProjectionCanSubmit
        ? "去确认并生成"
        : "输入股票代码";
  const quantProjectionOrdinaryProgressCheckpointItems: MetricItem[] = [
    {
      label: "当前 checkpoint",
      value: quantProjectionConfirmReplayStage,
      tone: quantProjectionSubmitError ? "bad" : quantProjectionSmallDataReady || taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : "warn"
    },
    {
      label: "P1 checkpoint",
      value: quantProjectionConfirmReplayStage,
      tone: quantProjectionSubmitError ? "bad" : quantProjectionSmallDataReady || taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : "warn"
    },
    {
      label: "确认标的",
      value: quantProjectionDisplaySymbol || "等待输入",
      tone: quantProjectionDisplaySymbol ? "good" : "neutral"
    },
    {
      label: "任务编号",
      value: quantProjectionDisplayTaskId || "等待确认按钮",
      tone: quantProjectionDisplayTaskId ? "good" : "warn"
    },
    {
      label: "下一步入口",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "结果状态",
      value: quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只读回放；确认按钮之外不创建 task；不交易、不改交易策略",
      tone: "good"
    }
  ];
  const quantProjectionUsableNowItems: MetricItem[] = [
    {
      label: "本地 FastAPI",
      value: quantProjectionP0Ready
        ? "已接上：可以输入代码并用确认按钮创建后台任务"
        : "未完全接上：先回 P0 一键启动预检",
      tone: quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "确认按钮",
      value: quantProjectionCanSubmit
        ? `可点击：${quantProjectionSymbolValidation.normalized} 将启动本地投研流程`
        : quantProjectionDisabledReason,
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "最近任务",
      value: quantProjectionDisplayTaskId || "等待点击确认按钮",
      tone: quantProjectionDisplayTaskId ? "good" : "warn"
    },
    {
      label: "结果回放",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? "已可读：打开股票量化推演和次日图谱回放本地结果"
        : quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "边用边看",
      value: quantProjectionProgressWatchLabel,
      tone: quantProjectionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "现在点哪",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "输入不外联；确认按钮才启动本地数据链；DeepSeek 解释随任务治理执行或安全降级；不交易、不改交易策略",
      tone: "good"
    }
  ];
  const candidateRadarUserFirstItems: MetricItem[] = [
    {
      label: "现在做什么",
      value: quantProjectionCanSubmit
        ? "点击确认并生成 3.0 量化推演"
        : quantProjectionP0Ready
          ? "先输入 6 位 A 股代码"
          : "先恢复本地 FastAPI 联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "输入状态",
      value: quantProjectionInputValidation,
      tone: quantProjectionSymbolReady ? "good" : searchSymbol.trim() ? "warn" : "neutral"
    },
    {
      label: "确认按钮",
      value: quantProjectionCanSubmit ? "可用：点击后才启动本地确认流程" : quantProjectionDisabledReason,
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "最近结果",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? quantProjectionOrdinaryResultSummary
        : quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "下一步入口",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "边界",
      value: "输入不外联；确认按钮才启动本地确认流程；外部数据或模型需单独授权；不交易、不改交易策略",
      tone: "good"
    }
  ];
  const candidateRadarOrdinaryVerticalSliceRows = [
    {
      步骤: "1. 搜票输入",
      当前状态: quantProjectionInputValidation,
      用户下一步: quantProjectionCanSubmit
        ? `点击确认 ${quantProjectionSymbolValidation.normalized} 并生成本地投研结果`
        : quantProjectionP0Ready
          ? "输入 6 位 A 股代码，等按钮启用后再确认"
          : "先恢复本地 FastAPI 联通",
      结果入口: "#candidate-radar-search-quant-projection",
      边界: "输入不会启动后台流程；只有确认按钮启动本地数据链；不调用外部数据或模型解释"
    },
    {
      步骤: "2. 确认任务",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: quantProjectionDisplayTaskId
        ? "看任务状态，成功后刷新本地回放"
        : quantProjectionCanSubmit
          ? "点击一次确认按钮，等待本地任务接收"
          : "先让输入和本地联通闸门通过",
      结果入口: quantProjectionDisplayTaskId || "等待确认按钮",
      边界: "确认按钮是唯一 P1 入口；本地缓存、页面渲染和搜索输入不创建第二个后台流程"
    },
    {
      步骤: "3. 最近结果",
      当前状态: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? quantProjectionOrdinaryResultSummary
        : quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      结果入口: "股票量化推演 / 次日图谱 / 候选池",
      边界: "结果只读回放 cache / call_ledger / packet；不补调外部数据或模型、不改交易策略"
    },
    {
      步骤: "4. 候选池",
      当前状态: ordinaryCandidateGroupLabel,
      用户下一步: ordinaryCandidateReviewOrder,
      结果入口: "#candidate-pool",
      边界: "Top/Watch/Excluded 都不是买入、卖出或加仓指令；只供研究复核"
    },
    {
      步骤: "5. 证据缺口",
      当前状态: ordinaryRetirementReadinessMainGaps,
      用户下一步: "继续本地 P1 搜票纵切；full-pool/deep-scan/provider/model 另行按钮任务",
      结果入口: "高级诊断默认收起",
      边界: "不把 scaffold、dry-run、execution-request、matrix、mock、sanitizer 或本地 receipt 当 production complete"
    }
  ];
  const ordinaryActiveDegradedRows = degradedModeRows.filter((row) =>
    row.active === true ||
    String(row.status ?? row.state ?? row.mode_state ?? "").includes("active")
  );
  const ordinaryActiveDegradedCount = Number(
    counts.degraded_mode_active_count ?? ordinaryActiveDegradedRows.length
  );
  const ordinaryActiveDegradedNames = ordinaryActiveDegradedRows
    .slice(0, 3)
    .map((row) => displayText(row.mode ?? row.mode_key ?? row.degraded_mode ?? row.status, "degraded"))
    .join(" / ");
  const ordinaryActiveDegradedLabel = ordinaryActiveDegradedCount
    ? `${ordinaryActiveDegradedCount}项 active degraded：${ordinaryActiveDegradedNames || "查看降级明细"}`
    : "未标记 active degraded";
  const ordinaryPreviousCacheStatusChangedCount = Number(
    resultDeltaClarity.status_changed_count ??
      resultDeltaClarity.candidate_status_changed_count ??
      counts.result_delta_status_changed_count ??
      previousCacheDiffRows.length
  );
  const ordinaryPreviousCacheDeltaLabel = resultDeltaClarity.previous_cache_diff_done === true
    ? `上一版候选 ${String(resultDeltaClarity.previous_candidate_count ?? "--")}；状态变化 ${ordinaryPreviousCacheStatusChangedCount}`
    : previousCacheDiffRows.length
      ? `已有 ${previousCacheDiffRows.length} 条 previous-cache diff；待浏览器视觉验收`
      : "等待上一版 cache diff";
  const ordinaryLiveLightFactoryNextStep = productionStageScopeManifest.production_radar_replacement_complete === true
    ? "进入最终 LTG-13/strict closeout 复核"
    : "继续用 P1 搜票确认；全池/深研和真实数据覆盖需未来显式 worker/provider task";
  const ordinaryLiveLightEvidenceFactoryItems: MetricItem[] = [
    {
      label: "缓存证据",
      value: candidateRadarCacheReady
        ? `${ordinaryCandidateGroupLabel}；最近 ${ordinaryLastCache}`
        : ordinaryCacheSourceLabel,
      tone: candidateRadarCacheReady ? "good" : "warn"
    },
    {
      label: "变化回看",
      value: ordinaryPreviousCacheDeltaLabel,
      tone: resultDeltaClarity.previous_cache_diff_done === true || previousCacheDiffRows.length ? "good" : "warn"
    },
    {
      label: "降级状态",
      value: ordinaryActiveDegradedLabel,
      tone: ordinaryActiveDegradedCount ? "warn" : "good"
    },
    {
      label: "替代进度",
      value: `direct evidence ${ordinaryRetirementReadinessDoneCount}/${ordinaryRetirementReadinessTotalCount || "--"}；pending ${ordinaryRetirementReadinessMissingCount}`,
      tone: ordinaryRetirementReadinessMissingCount ? "warn" : "good"
    },
    {
      label: "还缺证据",
      value: ordinaryRetirementReadinessMainGaps,
      tone: ordinaryRetirementReadinessMainGaps === "未标记关键阻断" ? "good" : "warn"
    },
    {
      label: "页面 QA",
      value: ordinaryBrowserQaStatusLabel,
      tone: browserQaReview.local_browser_qa_review_ready === true || browserQaEvidence.candidate_browser_qa_evidence_ready === true ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryLiveLightFactoryNextStep,
      tone: productionStageScopeManifest.production_radar_replacement_complete === true ? "good" : "warn"
    },
    {
      label: "非买入边界",
      value: "候选只用于研究复核；不是买入、卖出或加仓指令",
      tone: "good"
    }
  ];
  const ordinaryModeLayeredLiveLightItems: MetricItem[] = [
    {
      label: "cache/render 层",
      value: `${candidateRadarRuntimeModeLabel}；GET cache 和 React render 只读，不创建 task`,
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "button/task 层",
      value: quantProjectionCanSubmit
        ? `确认按钮可创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task`
        : quantProjectionP0Ready
          ? "等待有效代码；输入本身保持静默"
          : "先恢复 P0，本页不自动补证",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "provider/model 层",
      value: `${ordinaryTushareSourceLabel}；${ordinaryDeepSeekSourceLabel}`,
      tone: bootstrapLiveLight.tushare_on_open === true || bootstrapLiveLight.deepseek_on_open === true ? "warn" : "good"
    },
    {
      label: "worker/browser 层",
      value: `全池/深研/browser QA 需显式任务；当前页面 QA：${ordinaryBrowserQaStatusLabel}`,
      tone: browserQaReview.local_browser_qa_review_ready === true || browserQaEvidence.candidate_browser_qa_evidence_ready === true ? "good" : "warn"
    },
    {
      label: "production 层",
      value: `LTG-13 未关闭；${ordinaryRetirementReadinessMainGaps}`,
      tone: productionStageScopeManifest.production_radar_replacement_complete === true ? "good" : "warn"
    },
    {
      label: "交易隔离",
      value: "候选只供研究复核；不下单、不改持仓、不改 strategy action",
      tone: "good"
    }
  ];
  const candidateRadarCompactVerticalSliceItems: MetricItem[] = [
    {
      label: "输入到确认",
      value: quantProjectionCanSubmit
        ? `可确认 ${quantProjectionSymbolValidation.normalized}，点击后创建本地投研任务`
        : quantProjectionP0Ready
          ? "等待有效 A 股代码；输入本身保持静默"
          : "先恢复本地 FastAPI 联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "结果回放",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? quantProjectionOrdinaryResultSummary
        : quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "候选池",
      value: `${ordinaryCandidateGroupLabel}；${coarseFineSourceLabel}`,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "降级/缺口",
      value: ordinaryActiveDegradedCount
        ? `${ordinaryActiveDegradedLabel}；缺口：${ordinaryMissingEvidence}`
        : `无 active degraded；缺口：${ordinaryMissingEvidence}`,
      tone: ordinaryActiveDegradedCount || ordinaryMissingEvidence.includes("待补") || ordinaryMissingEvidence.includes("阻断") ? "warn" : "good"
    },
    {
      label: "下一步",
      value: ordinaryLiveLightFactoryNextStep,
      tone: productionStageScopeManifest.production_radar_replacement_complete === true ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只做本地投研证据回放；不是买入/卖出/加仓指令",
      tone: "good"
    }
  ];
  const candidateRadarCompactLeadCandidateItems: MetricItem[] = [
    {
      label: "先看一票",
      value: candidatePoolLeadCandidateDisplay,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "分组/评分",
      value: `${candidatePoolLeadCandidateGroup} / ${candidatePoolLeadCandidateScore}`,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "来源/缺口",
      value: `${candidatePoolLeadCandidateSource}；${candidatePoolLeadCandidateGap}`,
      tone: candidatePoolLeadCandidateGap.includes("缺") || candidatePoolLeadCandidateGap.includes("待补") || candidatePoolLeadCandidateGap.includes("阻断") ? "warn" : "good"
    },
    {
      label: "下一步",
      value: ordinaryCandidateTopCount ? "解释单票或继续看候选池" : candidatePoolPlainConclusionNext,
      tone: candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "边界",
      value: "首位候选只是复核对象；不预填、不提交、不买入",
      tone: "good"
    }
  ];
  const candidateRadarCompactRecentResultText =
    quantProjectionInterpretationReady || quantProjectionSmallDataReady
      ? quantProjectionOrdinaryResultSummary
      : quantProjectionP3OrdinaryReadableSentence;
  const candidateRadarCompactResultStatusLabel =
    quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "最近结果已回放" : "最近结果待回放";
  const candidateRadarCompactGroupStatusLabel =
    ordinaryCandidateTopCount ? "Top/Watch/Excluded 理由见下方速读" : "Top/Watch/Excluded 暂无理由";
  const candidateRadarCompactResultGroupItems: MetricItem[] = [
    {
      label: "最近结果",
      value: candidateRadarCompactRecentResultText,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "分组理由",
      value: candidateRadarCompactGroupStatusLabel,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "来源/缺口",
      value: `${coarseFineSourceLabel}；${candidatePoolPlainConclusionMissing}`,
      tone: candidatePoolPlainConclusionMissing.includes("缺") || candidatePoolPlainConclusionMissing.includes("待补") || candidatePoolPlainConclusionMissing.includes("阻断") ? "warn" : "good"
    },
    {
      label: "下一步",
      value: quantProjectionCanSubmit ? "确认当前输入，再看量化推演、次日图谱或 ETF/融资风险" : candidatePoolPlainConclusionNext,
      tone: quantProjectionCanSubmit || candidateRadarCacheGetReadable ? "good" : "warn"
    },
    {
      label: "边界",
      value: "结果和分组只做研究复核；不买卖、不加仓、不交易",
      tone: "good"
    }
  ];
  const candidateRadarCompactGroupDecisionItems: MetricItem[] = [
    {
      label: "Top 先看",
      value: candidateRadarGroupBriefText(candidateRadarTopBriefRow, "暂无 Top 候选；先看缺口"),
      tone: Object.keys(candidateRadarTopBriefRow).length ? "good" : "warn"
    },
    {
      label: "Watch 观察",
      value: candidateRadarGroupBriefText(candidateRadarWatchBriefRow, "暂无 Watch 候选；先看 Top 和缺口"),
      tone: Object.keys(candidateRadarWatchBriefRow).length ? "good" : "warn"
    },
    {
      label: "Excluded 排除/等待",
      value: candidateRadarGroupBriefText(candidateRadarExcludedBriefRow, "暂无 Excluded 记录；未标记排除原因"),
      tone: Object.keys(candidateRadarExcludedBriefRow).length ? "warn" : "neutral"
    },
    {
      label: "评分理由",
      value: ordinaryScoringReasonLabel,
      tone: Number(candidatePriorityExplanation.explained_candidate_count ?? 0) ? "good" : "warn"
    },
    {
      label: "边界",
      value: "分组只决定复核顺序；不是买入、卖出、加仓或清仓指令",
      tone: "good"
    }
  ];
  const candidateRadarCompactOperatorSubtitle = ordinaryCandidateTopCount && candidatePoolLeadCandidateTicker !== "暂无首位候选"
    ? `最近：${candidateRadarCompactResultStatusLabel}；先看一票：${candidatePoolLeadCandidateTicker}；${candidatePoolLeadCandidateGroup}；缺口：${candidatePoolLeadCandidateGap}；Top/Watch/Excluded 理由见下方速读`
    : candidateRadarCacheGetReadable
      ? `最近：${candidateRadarCompactResultStatusLabel}；候选池暂无候选；Top/Watch/Excluded 暂无理由；${candidatePoolPlainConclusionMissing}`
      : `最近：${candidateRadarCompactResultStatusLabel}；等待候选缓存；Top/Watch/Excluded 暂无理由；先确认一只股票或刷新本地回放`;
  const candidateRadarOpenNowPathItems: MetricItem[] = [
    {
      label: "候选池",
      value: `${ordinaryCandidateGroupLabel}；先看 Top / Watch / Excluded`,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "确认输入",
      value: quantProjectionCanSubmit
        ? `可确认 ${quantProjectionSymbolValidation.normalized}；点击后才创建本地投研任务`
        : quantProjectionP0Ready
          ? "输入有效 A 股代码；输入本身保持静默"
          : "先恢复本地 FastAPI 联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "最近结果",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? quantProjectionOrdinaryResultSummary
        : quantProjectionP3OrdinaryReadableSentence,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "下一步",
      value: quantProjectionDisplaySymbol
        ? "复核最近结果，必要时换一只票确认"
        : "先从候选池选一只，或直接输入代码确认",
      tone: quantProjectionDisplaySymbol || ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "非买入边界",
      value: "候选和推演只做研究复核；不是买入、卖出或加仓指令",
      tone: "good"
    }
  ];
  const candidateRadarVisibleNowItems: MetricItem[] = [
    {
      label: "现在能看到",
      value: `${ordinaryCandidateGroupLabel}；${candidatePoolPlainConclusionText}`,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "现在能操作",
      value: quantProjectionCanSubmit
        ? `确认 ${quantProjectionSymbolValidation.normalized} 并生成本地投研回放`
        : quantProjectionP0Ready
          ? "输入 6 位 A 股代码，等确认按钮启用"
          : "先恢复本地 FastAPI / cache 联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "运行模式",
      value: candidateRadarRuntimeModeLabel,
      tone: candidateRadarRuntimeModeLabel === "未知运行模式" ? "warn" : "good"
    },
    {
      label: "现在做什么",
      value: ordinaryPrimaryActionLabel,
      tone: candidateRadarP0Blocked ? "warn" : "good"
    },
    {
      label: "现在能跳转",
      value: "候选池 / 搜票确认 / 量化推演 / 次日图谱 / ETF 融资风险",
      tone: "good"
    },
    {
      label: "来源层",
      value: `${coarseFineSourceLabel}；${candidateRadarRuntimeModeLabel}`,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: "真实数据、权限、空窗口或本地结果缺口去数据能力页复核；本页不探测接口",
      tone: ordinaryProviderGapLabel.includes("缺口") || candidatePoolPlainConclusionStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "还缺什么",
      value: candidatePoolPlainConclusionMissing,
      tone: candidatePoolPlainConclusionStatus === "ready" ? "good" : "warn"
    },
    {
      label: "不会发生",
      value: "页面打开、搜索输入和本地跳转不会启动确认流程、不会刷新外部数据或模型、不会交易",
      tone: "good"
    }
  ];
  const candidateRadarTypedSymbolSentence = quantProjectionTaskReceiptInputMismatch
    ? `当前输入 ${quantProjectionSymbolValidation.normalized} 和最近结果 ${quantProjectionAcceptedTaskSymbol} 不一致；旧结果只作为参考，需要重新点击确认。`
    : quantProjectionSymbolReady
      ? `当前输入 ${quantProjectionSymbolValidation.normalized} 已通过本地格式校验；输入本身不会创建任务，确认按钮才进入本地投研链。`
      : searchSymbol.trim()
        ? `当前输入还没通过本地格式校验：${quantProjectionSymbolValidation.reason}；页面不会自动取数。`
        : "等待输入股票代码；页面先展示候选池和最近本地回放，不会自动取数。";
  const candidateRadarTypedSymbolItems: MetricItem[] = [
    {
      label: "当前输入",
      value: quantProjectionSymbolReady
        ? quantProjectionSymbolValidation.normalized
        : searchSymbol.trim()
          ? "格式待修正"
          : "等待 6 位 A 股代码",
      tone: quantProjectionSymbolReady ? "good" : searchSymbol.trim() ? "warn" : "neutral"
    },
    {
      label: "本地校验",
      value: quantProjectionSymbolReady
        ? "格式通过；还未启动确认流程"
        : searchSymbol.trim()
          ? `阻断：${quantProjectionSymbolValidation.reason}`
          : "输入框保持静默",
      tone: quantProjectionSymbolReady ? "good" : searchSymbol.trim() ? "warn" : "neutral"
    },
    {
      label: "最近结果归属",
      value: quantProjectionTaskReceiptInputMismatch
        ? `最近结果属于 ${quantProjectionAcceptedTaskSymbol}，当前输入需重新确认`
        : quantProjectionAcceptedTaskSymbol
          ? `最近结果属于 ${quantProjectionAcceptedTaskSymbol}`
          : "暂无可归属的最近确认结果",
      tone: quantProjectionTaskReceiptInputMismatch ? "warn" : quantProjectionAcceptedTaskSymbol ? "good" : "neutral"
    },
    {
      label: "确认按钮",
      value: quantProjectionCanSubmit
        ? `可确认 ${quantProjectionSymbolValidation.normalized}`
        : quantProjectionDisabledReason,
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "结果入口",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? "可去股票量化推演和次日图谱回放"
        : taskReceipt?.ok || quantProjectionPersistedTaskId
          ? "先看任务状态，成功后刷新本地回放"
          : "确认后再看量化推演、次日图谱和 ETF/融资风险",
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "不会发生",
      value: "输入和本地跳转不会启动确认流程、刷新外部数据或交易",
      tone: "good"
    }
  ];
  const candidateRadarTypedSymbolRows = [
    {
      检查项: "1. 输入股票",
      当前状态: candidateRadarTypedSymbolSentence,
      用户下一步: quantProjectionSymbolReady ? "检查确认按钮状态，再决定是否点击确认。" : "输入 6 位 A 股代码或带 SH/SZ/BJ 后缀的代码。",
      证据: "searchSymbol + normalizeAshareSymbolInput",
      边界: "输入只做本地校验；不会创建 task、不会调用 provider/model。"
    },
    {
      检查项: "2. 归属最近结果",
      当前状态: quantProjectionTaskReceiptInputMismatch
        ? `旧结果属于 ${quantProjectionAcceptedTaskSymbol}，当前输入 ${quantProjectionSymbolValidation.normalized} 需重新确认。`
        : quantProjectionAcceptedTaskSymbol
          ? `最近结果归属 ${quantProjectionAcceptedTaskSymbol}。`
          : "没有最近确认结果可归属。",
      用户下一步: quantProjectionTaskReceiptInputMismatch ? "重新确认当前输入，避免把旧结果当作当前票。" : "有最近结果时先作为历史参考。",
      证据: "taskReceipt payload_safe / search_quant_projection_receipt",
      边界: "页面不会取消旧 task，也不会把旧回执改写成新代码。"
    },
    {
      检查项: "3. 点击确认",
      当前状态: quantProjectionCanSubmit ? "确认按钮可用。" : quantProjectionDisabledReason,
      用户下一步: quantProjectionCanSubmit ? "点击一次确认并等待 TaskStatusPanel 或本地 cache 回写。" : "先处理禁用原因。",
      证据: "quantProjectionCanSubmit / quantProjectionP0Ready",
      边界: "只有确认按钮点击才进入 POST task；本卡片和链接不会启动数据链。"
    },
    {
      检查项: "4. 看结果",
      当前状态: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? "本地结果已有可读回放。"
        : taskReceipt?.ok || quantProjectionPersistedTaskId
          ? "等待任务或本地 cache 回放。"
          : "尚未确认，先看候选池和本地缓存。",
      用户下一步: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "打开量化推演、次日图谱和 ETF/融资风险。" : quantProjectionTushareDataCardNext,
      证据: "quantProjectionSmallDataReady / quantProjectionInterpretationReady / task receipt",
      边界: "结果入口只切换本地页面；不补调 Tushare、DeepSeek、GitHub，不交易。"
    }
  ];
  const candidateRadarConfirmButtonPrimarySentence = quantProjectionCanSubmit
    ? `确认按钮已可点：当前 ${quantProjectionSymbolValidation.normalized} 可以进入本地投研链；点击后先看本地进度和结果回放。`
    : quantProjectionP0Ready
      ? `确认按钮暂不可点：${quantProjectionDisabledReason}；输入有效 A 股代码后再确认。`
      : `确认按钮暂不可点：${quantProjectionDisabledReason}；先恢复本地 FastAPI / cache 联通。`;
  const candidateRadarConfirmButtonPrimaryItems: MetricItem[] = [
    {
      label: "当前输入",
      value: quantProjectionSymbolReady ? quantProjectionSymbolValidation.normalized : "等待有效 A 股代码",
      tone: quantProjectionSymbolReady ? "good" : "warn"
    },
    {
      label: "确认按钮",
      value: quantProjectionCanSubmit ? "可点击" : quantProjectionDisabledReason,
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "主动作",
      value: quantProjectionCanSubmit
        ? "去确认输入区点击一次确认并生成"
        : quantProjectionP0Ready
          ? "先修正输入，再看确认按钮"
          : "先恢复本地联通，再回确认输入区",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "提交后看",
      value: taskReceipt?.ok || quantProjectionPersistedTaskId ? "本地进度和最近投研结果" : "本地进度、量化推演和次日图谱",
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId || quantProjectionCanSubmit ? "good" : "neutral"
    },
    {
      label: "禁用原因",
      value: quantProjectionSubmitDisabled ? quantProjectionDisabledReason : "按钮可用；仍需用户手动点击",
      tone: quantProjectionSubmitDisabled ? "warn" : "good"
    },
    {
      label: "不会发生",
      value: "这张卡不提交、不启动确认流程、不刷新外部数据或模型",
      tone: "good"
    },
    {
      label: "边界",
      value: "确认只启动本地研究流程；不是买入、卖出、加仓或融资指令",
      tone: "good"
    }
  ];
  const candidateRadarConfirmButtonPrimaryRows = [
    {
      读法: "1. 输入校验",
      当前状态: quantProjectionInputValidation,
      用户下一步: quantProjectionSymbolReady ? "看确认按钮是否可点。" : "输入 6 位 A 股代码或带 .SZ/.SH/.BJ 后缀。",
      证据: "searchSymbol / normalizeAshareSymbolInput",
      边界: "输入只做本地校验；不会创建 task、不会调用 provider/model。"
    },
    {
      读法: "2. 按钮状态",
      当前状态: quantProjectionCanSubmit ? "确认按钮可点。" : quantProjectionDisabledReason,
      用户下一步: quantProjectionCanSubmit ? "跳到确认输入区，点击一次确认并生成。" : "先处理禁用原因。",
      证据: "quantProjectionCanSubmit / quantProjectionSubmitDisabled",
      边界: "只有原确认按钮 onClick 会创建本地 POST task；本卡片链接不会提交。"
    },
    {
      读法: "3. 点击后看",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: "看 TaskStatusPanel、最近投研结果、量化推演和次日图谱。",
      证据: "taskReceipt / taskIndex / quant projection cache replay",
      边界: "状态和结果只读本地 task/cache/ledger/packet；不会补调 provider/model。"
    },
    {
      读法: "4. 安全边界",
      当前状态: "确认按钮是本地研究入口，不是交易入口。",
      用户下一步: "需要换票时回确认输入区重新输入并确认。",
      证据: "local route anchors + POST task boundary copy",
      边界: "不交易、不改持仓、不改 strategy action。"
    }
  ];
  const candidateRadarOnePathSentence = taskReceipt?.ok || quantProjectionPersistedTaskId
    ? "已有本地确认进度或历史结果：按本地进度、最近结果、Factor/Next 和 ETF/融资风险一条线复核。"
    : quantProjectionCanSubmit
      ? `下一票主路径已就绪：确认 ${quantProjectionSymbolValidation.normalized} 后，先看本地进度，再看最近结果和三面回放。`
      : "下一票主路径等待输入或本地联通：先让确认按钮可用，再按进度、结果、风险顺序看。";
  const candidateRadarOnePathItems: MetricItem[] = [
    {
      label: "1. 确认",
      value: quantProjectionCanSubmit ? `可确认 ${quantProjectionSymbolValidation.normalized}` : quantProjectionDisabledReason,
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "2. 进度",
      value: taskReceipt?.ok || quantProjectionPersistedTaskId ? quantProjectionLatestUserProgress : "确认后看本地进度 / 任务目录",
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionCanSubmit ? "neutral" : "warn"
    },
    {
      label: "3. 结果",
      value: quantProjectionP2P3ConnectionReady ? "P2/P3 可回放：量化推演和次日图谱" : quantProjectionReplayDestinationState,
      tone: quantProjectionP2P3ConnectionReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "4. 风险",
      value: "最后看数据能力和 ETF/融资风险预算；不生成加仓或融资指令",
      tone: "good"
    },
    {
      label: "不会发生",
      value: "这张路径卡不会提交、不会启动确认流程、不会刷新外部数据或模型",
      tone: "good"
    },
    {
      label: "边界",
      value: "下一票只是研究复核路径，不是买入、卖出、加仓、融资或下单指令",
      tone: "good"
    }
  ];
  const candidateRadarOnePathRows = [
    {
      步骤: "1. 输入并确认",
      当前状态: quantProjectionCanSubmit ? `确认按钮可用：${quantProjectionSymbolValidation.normalized}` : quantProjectionDisabledReason,
      用户下一步: quantProjectionCanSubmit ? "跳到确认输入区，点击一次确认并生成。" : "先让 P0 联通和股票代码校验通过。",
      入口: "#candidate-radar-search-quant-projection",
      边界: "只有真正确认按钮会 POST；本路径卡只是本地链接和读法。"
    },
    {
      步骤: "2. 看任务",
      当前状态: taskReceipt?.ok || quantProjectionPersistedTaskId ? quantProjectionLatestTaskState : "等待确认后生成本地任务",
      用户下一步: "打开任务目录或首屏 TaskStatusPanel，看是否接收和回写。",
      入口: "#tasks",
      边界: "任务状态只轮询本地 FastAPI；不创建第二个 task。"
    },
    {
      步骤: "3. 回放结果",
      当前状态: quantProjectionP2P3ConnectionReady ? "P2/P3 已可回放" : quantProjectionReplayDestinationState,
      用户下一步: "先看量化推演支持/压制，再看次日图谱。",
      入口: "#factor / #next",
      边界: "结果回放只读 cache / ledger / packet；不补调 provider/model。"
    },
    {
      步骤: "4. 补看风险",
      当前状态: "数据能力 + ETF/融资风险预算",
      用户下一步: "复核 Tushare ledger、权限、空窗口、degraded 原因和融资约束。",
      入口: "DATA_CAPABILITY_HREF / #marginEtf",
      边界: "风险入口只读本地状态；不交易、不下单、不改 strategy action。"
    }
  ];
  const candidateRadarRecentResearchResultSentence =
    searchQuantDegradedResultVisible && searchQuantResultCurrentSymbol && searchQuantDegradedResultSymbol && searchQuantResultCurrentSymbol !== searchQuantDegradedResultSymbol
      ? `最近尝试 ${searchQuantDegradedResultSymbol} 已降级；当前可用结果仍保留 ${searchQuantResultCurrentSymbol}，旧任务不会覆盖 current。`
      : quantProjectionInterpretationReady || quantProjectionSmallDataReady
      ? `最近投研结果可回放：${quantProjectionOrdinaryResultSummary}`
      : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? `最近投研结果正在回写：${quantProjectionReplayDestinationState}`
        : quantProjectionCanSubmit
          ? `当前 ${quantProjectionSymbolValidation.normalized} 可以确认；确认后这里会显示最近投研结果、来源和缺口。`
          : "最近投研结果等待确认；当前先看候选池和本地缓存，不会自动取数。";
  const candidateRadarRecentResearchResultItems: MetricItem[] = [
    {
      label: "最近结果",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? quantProjectionOrdinaryResultSummary
        : quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "当前可用",
      value: searchQuantCurrentResultLabel,
      tone: searchQuantCurrentResultVersion ? "good" : "warn"
    },
    {
      label: "最新尝试",
      value: searchQuantLatestTaskResultLabel,
      tone: searchQuantLatestTaskResultVersion ? (searchQuantDegradedResultVisible ? "warn" : "good") : "warn"
    },
    {
      label: "last-good",
      value: searchQuantLastGoodResultLabel,
      tone: searchQuantResultVersionSummary.last_good_result_available === true || searchQuantLastGoodResultVersion ? "good" : "warn"
    },
    {
      label: "覆盖保护",
      value: searchQuantResultVersionSummary.old_task_can_overwrite_current === false || searchQuantResultLineage.old_task_can_overwrite_current === false
        ? "旧任务不能覆盖当前结果"
        : "等待 symbol + result_version 保护",
      tone: searchQuantResultVersionSummary.old_task_can_overwrite_current === false || searchQuantResultLineage.old_task_can_overwrite_current === false ? "good" : "warn"
    },
    {
      label: "结果归属",
      value: quantProjectionLastResult,
      tone: quantProjectionDisplaySymbol || quantProjectionPersistedTaskId || taskReceipt?.ok ? "good" : "neutral"
    },
    {
      label: "当前票",
      value: quantProjectionDisplaySymbol || quantProjectionAcceptedTaskSymbol || "等待确认股票",
      tone: quantProjectionDisplaySymbol || quantProjectionAcceptedTaskSymbol ? "good" : "neutral"
    },
    {
      label: "最近任务",
      value: quantProjectionLatestUserProgress,
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId || taskIndexLatestConfirmedTaskId ? "good" : quantProjectionSubmitError ? "bad" : "neutral"
    },
    {
      label: "P2/P3 去向",
      value: quantProjectionP2P3ConnectionReady ? "可回放：先量化推演，再次日图谱" : quantProjectionProgressWatchNext,
      tone: quantProjectionP2P3ConnectionReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "来源状态",
      value: quantProjectionSourcePlainStatus,
      tone: quantProjectionProviderLedgerReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: "真实数据、权限、空窗口和降级原因去数据能力页复核",
      tone: quantProjectionProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "degraded / 缺口",
      value: `${ordinaryActiveDegradedLabel}；${quantProjectionMissingEvidence}`,
      tone: ordinaryActiveDegradedCount || quantProjectionMissingEvidence.includes("待补") || quantProjectionMissingEvidence.includes("阻断") ? "warn" : "good"
    },
    {
      label: "下一步",
      value: quantProjectionReplayDestinationNextStep,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "研究边界",
      value: "结果卡只读本地结果记录；不是买入、卖出或加仓指令",
      tone: "good"
    }
  ];
  const candidateRadarRecentResearchResultRows = [
    {
      读法: "1. 先看结论",
      当前状态: quantProjectionOrdinaryResultSummary,
      用户下一步: quantProjectionOrdinaryResultNext,
      证据: quantProjectionOrdinaryResultEvidence,
      边界: quantProjectionOrdinaryResultBoundary
    },
    {
      读法: "2. 再看来源",
      当前状态: `${quantProjectionCacheSourceLabel} / ${quantProjectionProviderSourceLabel} / ${quantProjectionModelSourceLabel}`,
      用户下一步: quantProjectionProviderLedgerReady ? "回放量化推演和次日图谱。" : "等待确认任务或真实数据授权后的后台回写。",
      证据: quantProjectionProviderCallSource,
      边界: "来源只读本地 cache / call_ledger / packet；不会从结果卡补调 provider/model。"
    },
    {
      读法: "3. 识别降级",
      当前状态: searchQuantDegradedResultVisible
        ? `${searchQuantDegradedResultLabel}；current=${searchQuantCurrentResultLabel}；last-good=${searchQuantLastGoodResultLabel}`
        : `${ordinaryActiveDegradedLabel}；${quantProjectionBlockedState}`,
      用户下一步: searchQuantDegradedResultVisible
        ? "先看 current/last-good 结果；最新 degraded 只用于复核缺口和重试条件。"
        : quantProjectionMissingEvidence,
      证据: "search_quant_result_version_summary / degraded_mode_rows / search_quant_projection_receipt",
      边界: "degraded 和 missing evidence 只提示待补证据；旧任务不能覆盖当前结果，不创建 task、不升级 production complete。"
    },
    {
      读法: "4. 去哪里看",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      证据: "ordinary_replay_destination_rows / local route anchors",
      边界: quantProjectionReplayBoundary
    },
    {
      读法: "5. 当前票和任务",
      当前状态: `${quantProjectionDisplaySymbol || "等待确认股票"}；${quantProjectionLatestTaskState}`,
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId || taskIndexLatestConfirmedTaskId
        ? "先看 TaskStatusPanel 或最近任务回放，再刷新本地 cache。"
        : quantProjectionCanSubmit
          ? "点击确认按钮生成当前票的本地投研任务。"
          : "先输入有效 A 股代码或恢复本地联通。",
      证据: "searchSymbol / taskReceipt / taskIndex / search_quant_projection_receipt",
      边界: "这行只读当前票和本地任务索引；不提交、不轮询外部、不补调 provider/model。"
    },
    {
      读法: "6. P2/P3 回放",
      当前状态: quantProjectionP2P3ConnectionReady ? "P2 三面和 P3 结果已经连到同一条本地确认链。" : quantProjectionProgressWatchNext,
      用户下一步: quantProjectionP2P3ConnectionReady ? "打开量化推演和次日图谱，只读复核结果。" : quantProjectionTushareFirstOrdinaryNextStep,
      证据: "quantProjectionP2P3ConnectionReady / Factor / Next local cache",
      边界: "P2/P3 去向只切换本地结果页；不创建第二个 task、不交易、不改 strategy action。"
    }
  ];
  const candidatePoolEmptyStatePrimarySentence = candidatePoolPlainConclusionStatus === "empty_cache"
    ? "候选池为空：现在先回确认输入区输入一只 A 股，点确认后等待本地投研结果；这张卡本身不创建任务。"
    : candidatePoolPlainConclusionStatus === "p0_check"
      ? "候选池暂不可读：先恢复本地连接，再回候选池或确认输入区。"
      : `候选池已有复核对象：先看 ${candidatePoolLeadCandidateDisplay}；需要换票再回确认输入区。`;
  const candidatePoolEmptyStatePrimaryItems: MetricItem[] = [
    {
      label: "当前状态",
      value: candidatePoolPlainConclusionText,
      tone: candidatePoolPlainConclusionStatus === "ready" ? "good" : "warn"
    },
    {
      label: "主动作",
      value: quantProjectionCanSubmit
        ? `回确认输入区，点击确认 ${quantProjectionSymbolValidation.normalized}`
        : quantProjectionP0Ready
          ? "回确认输入区，输入 6 位 A 股代码后再确认"
          : "先恢复本地 FastAPI / cache 联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "可回放",
      value: quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "来源",
      value: `${coarseFineSourceLabel}；GET cache 只读`,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "缺口",
      value: candidatePoolPlainConclusionMissing,
      tone: candidatePoolPlainConclusionStatus === "ready" ? "good" : "warn"
    },
    {
      label: "不会发生",
      value: "本卡片不快扫、不 POST、不调用 provider/model/worker",
      tone: "good"
    },
    {
      label: "边界",
      value: ordinaryCandidateGroupBoundary,
      tone: "good"
    }
  ];
  const candidatePoolEmptyStatePrimaryRows = [
    {
      读法: "1. 空候选判断",
      当前状态: `${candidatePoolPlainConclusionStatus}；${ordinaryCandidateGroupLabel}`,
      用户下一步: candidatePoolPlainConclusionStatus === "empty_cache"
        ? "先回确认输入区输入或确认一只股票。"
        : "先按已有候选或当前阻断状态复核。",
      证据: "candidate_rows length / top_watch_excluded_group_rows / candidatePoolPlainConclusionStatus",
      边界: "空候选只说明本地候选 cache 暂无对象；不是全市场扫描结论。"
    },
    {
      读法: "2. 主动作",
      当前状态: quantProjectionCanSubmit ? `确认按钮可用于 ${quantProjectionSymbolValidation.normalized}` : quantProjectionDisabledReason,
      用户下一步: quantProjectionCanSubmit ? "点击确认按钮，等待 TaskStatusPanel 或本地 cache 回写。" : "先处理输入格式或本地联通阻断。",
      证据: "quantProjectionCanSubmit / normalizeAshareSymbolInput",
      边界: "只有确认按钮才创建本地投研 task；本卡片链接不创建 task。"
    },
    {
      读法: "3. 本地回放",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: "有结果就看量化推演和次日图谱；没有结果就回确认输入。",
      证据: "task receipt / quant projection cache replay",
      边界: "回放只读本地 cache / ledger / packet；不会补调 Tushare、DeepSeek 或 GitHub。"
    },
    {
      读法: "4. 边界",
      当前状态: ordinaryCandidateGroupBoundary,
      用户下一步: "候选、推演和图谱都只作为研究复核入口。",
      证据: "local route anchors only",
      边界: "不交易、不改持仓、不改 strategy action，不把空候选变成买入建议。"
    }
  ];
  const candidateRadarUserRouteQaSummary = candidateRadarUserRouteQaPassed
    ? `本轮本地路线 QA 已覆盖下一票雷达：${userRouteQaCoveredViewports.join(" / ") || "desktop / mobile"}，打开和输入未创建任务。`
    : userRouteQaEvidence.latest_report_status
      ? `已有本地路线 QA 报告，但下一票雷达仍需复核：${displayText(userRouteQaEvidence.latest_report_status)}。`
      : "等待本地路线 QA 报告；不影响当前候选缓存和确认按钮使用。";
  const candidateRadarUserRouteQaItems: MetricItem[] = [
    {
      label: "路线 QA",
      value: candidateRadarUserRouteQaPassed ? "下一票雷达已通过本地路线 QA" : "等待下一票雷达路线 QA",
      tone: candidateRadarUserRouteQaPassed ? "good" : "warn"
    },
    {
      label: "视口",
      value: userRouteQaCoveredViewports.length ? userRouteQaCoveredViewports.join(" / ") : "等待 desktop / mobile",
      tone: userRouteQaCoveredViewports.includes("desktop") && userRouteQaCoveredViewports.includes("mobile") ? "good" : "warn"
    },
    {
      label: "路线",
      value: userRouteQaCoveredRoutes.includes("#candidates")
        ? `${userRouteQaCoveredRoutes.length} 条普通路线已覆盖`
        : "等待 #candidates 覆盖",
      tone: userRouteQaCoveredRoutes.includes("#candidates") ? "good" : "warn"
    },
    {
      label: "输入静默",
      value: userRouteQaEvidence.typing_silence_verified === true && !userRouteQaTaskSilenceFailedCount
        ? "搜索输入和页面渲染未创建任务"
        : `需复核 ${userRouteQaTaskSilenceFailedCount} 条任务静默`,
      tone: userRouteQaEvidence.typing_silence_verified === true && !userRouteQaTaskSilenceFailedCount ? "good" : "warn"
    },
    {
      label: "最新报告",
      value: `${userRouteQaLatestPassedCount}/${userRouteQaLatestMatrixCount || "--"} passed；review ${userRouteQaLatestReviewRequiredCount}；console ${userRouteQaLatestConsoleErrorCount}`,
      tone: userRouteQaEvidence.latest_report_passed === true ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读 ignored 本地 QA 摘要；不是 provider、CI 或旧雷达退场证据",
      tone: "good"
    }
  ];
  const candidateRadarUserRouteQaRows = [
    {
      检查项: "1. 打开候选页",
      当前状态: candidateRadarUserRouteQaPassed ? "latest local route QA passed" : "waiting local route QA",
      用户下一步: "先看候选池、确认输入和非买入边界；需要补证再看审计区",
      证据: "user_route_qa_evidence_contract.latest_report_candidate_route_passed",
      边界: "只读 ignored 本地报告摘要；普通页不打开浏览器、不写截图"
    },
    {
      检查项: "2. 视口覆盖",
      当前状态: userRouteQaCoveredViewports.length ? userRouteQaCoveredViewports.join(" / ") : "waiting desktop/mobile",
      用户下一步: "desktop/mobile 都通过后，再把普通入口问题转成具体 UI 修复",
      证据: "covered_viewports",
      边界: "本地视口 evidence 不是 durable CI 或 packaged-runtime evidence"
    },
    {
      检查项: "3. 输入静默",
      当前状态: userRouteQaEvidence.typing_silence_verified === true && !userRouteQaTaskSilenceFailedCount
        ? "typing/render task silence verified"
        : "typing silence review required",
      用户下一步: "输入股票代码前先确认不会自动创建任务；确认按钮才是工作入口",
      证据: "typing_silence_verified + task_silence_failed_count",
      边界: "输入、GET cache、React render 不调用 Tushare、DeepSeek、GitHub、worker 或交易路径"
    }
  ];
  const candidateRadarPostConfirmNextStepSentence = quantProjectionFactorNextReady
    ? `${quantProjectionProgressWatchSymbol || quantProjectionDisplaySymbol || "当前标的"} 确认后已可回放：先看股票量化推演支持/压制，再看次日图谱，涉及仓位或融资预算时再看 ETF/融资风险。`
    : quantProjectionInterpretationReady || quantProjectionSmallDataReady
      ? `${quantProjectionProgressWatchSymbol || quantProjectionDisplaySymbol || "当前标的"} 已有本地结果线索：先读 P3 结果和 P2 三面；量化推演或次日图谱仍等待本地回放时，就按降级提示处理。`
      : ordinaryCandidateTopCount
        ? `先从候选池选一只，例如 ${candidatePoolLeadCandidateDisplay}，回确认输入区点击确认；成功后再看量化推演、次日图谱和 ETF/融资风险。`
        : "确认后下一步等待候选或输入：先恢复本地 cache 或输入 A 股代码，确认按钮才会创建本地投研任务。";
  const candidateRadarPostConfirmNextStepItems: MetricItem[] = [
    {
      label: "候选来源",
      value: ordinaryCandidateGroupLabel,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "确认动作",
      value: quantProjectionCanSubmit
        ? `可确认 ${quantProjectionSymbolValidation.normalized}`
        : quantProjectionP0Ready
          ? "输入有效 A 股代码后再确认"
          : "先恢复本地联通",
      tone: quantProjectionCanSubmit || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "先看量化推演",
      value: quantProjectionFactorNextReady || quantProjectionInterpretationReady
        ? "支持/压制摘要可作为第一站回放"
        : "等待确认结果或本地 cache 回写",
      tone: quantProjectionFactorNextReady || quantProjectionInterpretationReady ? "good" : "warn"
    },
    {
      label: "再看次日图谱",
      value: quantProjectionFactorNextReady
        ? "次日图谱可复核路径、参考线和操作区"
        : "等待 P3 回放后再打开次日图谱",
      tone: quantProjectionFactorNextReady ? "good" : "warn"
    },
    {
      label: "Factor/Next 对齐",
      value: quantProjectionCrossModuleAlignmentSummary,
      tone: quantProjectionCrossModuleAlignmentTone
    },
    {
      label: "风险补看",
      value: "ETF/融资风险只读本地预算，不生成加仓或加融资指令",
      tone: "good"
    },
    {
      label: "边界",
      value: "这些入口只切换本地页面或锚点，不创建第二个 task、不调用 Tushare/DeepSeek、不交易",
      tone: "good"
    }
  ];
  const candidateRadarSingleTicketLoopSentence =
    quantProjectionInterpretationReady || quantProjectionSmallDataReady
      ? `单票闭环已有结果：${quantProjectionResultSymbol || "当前标的"} 先看最近结果，再去 Factor、Next 和 ETF/融资风险做只读复核。`
      : taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "单票闭环正在回放：先看本地进度，完成后刷新本地结果，再看量化推演、次日图谱和 ETF/融资风险。"
        : ordinaryCandidateTopCount
          ? `单票闭环从 Top 开始：先解释 ${candidatePoolLeadCandidateDisplay}，确认输入后看任务进度和最近结果。`
          : "单票闭环等待候选或输入：先回确认输入区，确认按钮才会创建本地投研任务。";
  const candidateRadarSingleTicketLoopItems: MetricItem[] = [
    {
      label: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "1. 确认股票" : "1. 解释 Top",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? `${quantProjectionResultSymbol || "当前标的"} 已有本地结果`
        : ordinaryCandidateTopCount ? candidatePoolLeadCandidateDisplay : "暂无 Top；先看候选池或输入单票",
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "2. 确认输入",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady
        ? `最近结果归属 ${quantProjectionResultSymbol || "当前标的"}；换票时回确认输入区重新输入并点击确认`
        : quantProjectionCanSubmit ? `可确认 ${quantProjectionSymbolValidation.normalized}` : quantProjectionDisabledReason,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady || quantProjectionCanSubmit ? "good" : quantProjectionP0Ready ? "neutral" : "warn"
    },
    {
      label: "3. 任务进度",
      value: taskReceipt?.ok || quantProjectionPersistedTaskId ? quantProjectionLatestUserProgress : "确认后看本地进度 / 任务目录",
      tone: taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : quantProjectionCanSubmit ? "neutral" : "warn"
    },
    {
      label: "4. 最近结果",
      value: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? quantProjectionOrdinaryResultSummary : quantProjectionReplayDestinationState,
      tone: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral"
    },
    {
      label: "5. 后续入口",
      value: quantProjectionP2P3ConnectionReady ? "量化推演 -> 次日图谱 -> ETF/融资风险只读复核" : "结果待回放时先看量化推演 / 次日图谱的降级提示",
      tone: quantProjectionP2P3ConnectionReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "闭环卡只切换本地页面或锚点；不启动第二个后台流程、不刷新外部数据或模型、不交易",
      tone: "good"
    }
  ];
  const ordinaryCandidateReviewCompassItems: MetricItem[] = [
    {
      label: "先看哪组",
      value: ordinaryCandidateGroupLabel,
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "怎么复核",
      value: "先看 Top，再看 Watch，最后看 Excluded 和缺口；不要从工程审计表开始",
      tone: "good"
    },
    {
      label: "看哪三列",
      value: "分组 / 来源 / 缺口",
      tone: "good"
    },
    {
      label: "来源状态",
      value: coarseFineSourceLabel,
      tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn"
    },
    {
      label: "下一步",
      value: quantProjectionDisplaySymbol ? "复核最近结果，必要时换一只票确认" : "需要单票解释时输入代码并确认",
      tone: quantProjectionDisplaySymbol || quantProjectionP0Ready ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "候选只进入研究复核，不是买入、卖出或加仓指令",
      tone: "good"
    }
  ];
  const ordinaryCandidateReviewCompassRows = [
    {
      复核顺序: "1. Top",
      用户看法: "优先看候选理由和来源是否清楚",
      入口: "#candidate-pool",
      边界: "Top 只表示优先复核，不是买入指令"
    },
    {
      复核顺序: "2. Watch",
      用户看法: "观察触发条件、缺口和是否等待更多证据",
      入口: "#candidate-pool",
      边界: "Watch 不是加仓或追买提示"
    },
    {
      复核顺序: "3. Excluded",
      用户看法: "先看排除原因，避免把缺数据误读成低风险",
      入口: "#candidate-pool",
      边界: "Excluded 不会改交易策略，也不会删除旧证据"
    },
    {
      复核顺序: "4. 单票解释",
      用户看法: "需要解释时输入股票代码并点击确认",
      入口: "#candidate-radar-search-quant-projection",
      边界: "输入保持静默；只有确认按钮创建本地任务"
    }
  ];
  const ordinaryCandidateGroupActionSentence = ordinaryCandidateTopCount
    ? `分组已可读：Top ${ordinaryCandidateTopCount} 先解释首位候选，Watch ${ordinaryCandidateWatchCount} 只观察触发条件，Excluded ${ordinaryCandidateExcludedCount} 先看排除原因。`
    : "候选分组暂无可操作对象：先回确认输入区，或等待本地候选 cache 回放；不要把空池当交易信号。";
  const ordinaryCandidateGroupActionItems: MetricItem[] = [
    {
      label: "Top 下一步",
      value: ordinaryCandidateTopCount
        ? `先解释 ${candidatePoolLeadCandidateDisplay}`
        : "等待 Top 候选",
      tone: ordinaryCandidateTopCount ? "good" : "warn"
    },
    {
      label: "Watch 下一步",
      value: ordinaryCandidateWatchCount
        ? "只观察触发条件和缺口，不追买、不加仓"
        : "当前无 Watch，继续看 Top 或输入单票",
      tone: ordinaryCandidateWatchCount ? "good" : "neutral"
    },
    {
      label: "Excluded 下一步",
      value: ordinaryCandidateExcludedCount
        ? "先看排除原因，避免把缺数据误读成低风险"
        : "当前无 Excluded，仍保留排除边界",
      tone: ordinaryCandidateExcludedCount ? "warn" : "neutral"
    },
    {
      label: "结果入口",
      value: "解释单票后看 Factor、Next 和 ETF/融资风险",
      tone: "good"
    },
    {
      label: "数据缺口",
      value: coarseFineGapLabel,
      tone: Number(coarseFineScreening.gap_visible_count ?? 0) ? "warn" : "good"
    },
    {
      label: "不会发生",
      value: "本行动条只切换本地页面；不快扫、不 POST、不调用 provider/model/worker、不交易",
      tone: "good"
    }
  ];
  const ordinaryCandidateGroupActionRows = [
    {
      分组: "Top",
      用户动作: ordinaryCandidateTopCount ? "解释首位候选或继续看候选池理由。" : "等待 Top 候选或回确认输入区。",
      入口: ordinaryCandidateTopCount ? "#candidate-radar-search-quant-projection" : "#candidate-pool",
      边界: "Top 只是优先复核，不是买入、加仓或融资指令。"
    },
    {
      分组: "Watch",
      用户动作: "只观察触发条件、来源和缺口；需要单票解释时仍要手动确认。",
      入口: "#candidate-pool",
      边界: "Watch 不代表追买、不代表提高仓位，也不会改交易策略。"
    },
    {
      分组: "Excluded",
      用户动作: "先看排除原因和缺失证据；不要把排除行当作自动清仓信号。",
      入口: "#candidate-pool",
      边界: "Excluded 只保留研究排除理由；不删除旧证据、不创建交易动作。"
    },
    {
      分组: "结果回放",
      用户动作: "确认单票后再看 Factor、Next、数据能力和 ETF/融资风险。",
      入口: "#factor / #next / #dataCapability / #marginEtf",
      边界: "结果入口只读本地 cache / packet；不创建第二个 task、不补调外部数据。"
    }
  ];
  const quantProjectionPostConfirmReplayContractReady =
    quantProjectionPostConfirmReplayContract.schema_version === "candidate_radar_search_quant_projection_post_confirm_replay_contract.v1";
  const quantProjectionPostConfirmReplaySequence = Array.isArray(quantProjectionPostConfirmReplayContract.readback_sequence)
    ? quantProjectionPostConfirmReplayContract.readback_sequence.map(String).join(" -> ")
    : "等待确认后的回放顺序";
  const quantProjectionPostConfirmReplaySurfaces = Array.isArray(quantProjectionPostConfirmReplayContract.writeback_surfaces)
    ? quantProjectionPostConfirmReplayContract.writeback_surfaces.map(String).join(" / ")
    : "cache / call_ledger / packet";
  const quantProjectionPostConfirmReplayAnchors = Array.isArray(quantProjectionPostConfirmReplayContract.result_anchors)
    ? quantProjectionPostConfirmReplayContract.result_anchors.map(String).join(" / ")
    : "#tasks / #factor / #next";
  const quantProjectionPostConfirmReplayContractRows = [
    {
      合同项: "任务回执",
      当前状态: quantProjectionPostConfirmReplayContractReady ? "确认后的回放顺序已返回" : "等待确认按钮返回回放顺序",
      用户下一步: quantProjectionPostConfirmReplayContractReady ? "按合同顺序看 task id、TaskStatusPanel 和本地回放" : "输入有效代码并点击确认",
      证据: "ordinary_post_confirm_replay_contract",
      边界: "合同只描述确认后的只读回放；不会从本表创建第二个 task"
    },
    {
      合同项: "回放顺序",
      当前状态: quantProjectionPostConfirmReplaySequence,
      用户下一步: "先看任务编号，再等 TaskStatusPanel success，最后刷新本地 cache",
      证据: "readback_sequence",
      边界: "GET cache / bootstrap status 只读；React render 不补调 provider/model"
    },
    {
      合同项: "P2 三面",
      当前状态: quantProjectionPostConfirmReplaySurfaces,
      用户下一步: "确认 cache、call_ledger、packet 是否可回放",
      证据: "writeback_surfaces",
      边界: "call_ledger 只由 POST task / worker 产生；普通回放不展示凭据或 raw log"
    },
    {
      合同项: "结果入口",
      当前状态: quantProjectionPostConfirmReplayAnchors,
      用户下一步: "任务成功后打开任务进度、量化推演和次日图谱",
      证据: "result_anchors",
      边界: "结果入口只切换本地模块；不交易、不下单、不改交易策略"
    }
  ];
  const quantProjectionFirstScreenTaskContractItems: MetricItem[] = [
    {
      label: "POST 路由",
      value: "POST /api/candidate-radar/quant-projection",
      tone: quantProjectionCanSubmit ? "good" : "warn"
    },
    {
      label: "task_type",
      value: "run_candidate_radar_quant_projection",
      tone: "good"
    },
    {
      label: "触发方式",
      value: "只在确认按钮点击后创建；输入、页面打开、React render 和 GET cache 静默",
      tone: "good"
    },
    {
      label: "写回三面",
      value: "cache / call_ledger / packet",
      tone: quantProjectionSmallDataReady ? "good" : "warn"
    },
    {
      label: "DeepSeek",
      value: "skipped，等 governed executor；不作为数据源或动作",
      tone: "good"
    },
    {
      label: "交易边界",
      value: "不真实交易、不下单、不改 strategy action；不改交易策略",
      tone: "good"
    }
  ];
  const quantProjectionConfirmedChainQuickRows = [
    {
      链路节点: "1. 点击确认",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: quantProjectionCanSubmit || taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "点击一次确认后看 task id 和 TaskStatusPanel；不要从输入框或刷新页面期待自动补数"
        : "先输入有效 A 股代码；输入本身保持静默",
      证据: taskReceipt?.ok || quantProjectionPersistedTaskId ? "task receipt / candidate_radar_cache_packet" : "local input validation",
      边界: "只有确认按钮会创建 POST task；页面打开、搜索输入、React render 和 GET cache 不外联"
    },
    {
      链路节点: "2. Tushare-first",
      当前状态: quantProjectionProviderLedgerReady
        ? `Tushare-first ledger 已回放：${quantProjectionProviderApiSuccessLabel}/${quantProjectionProviderApiTotalLabel} 个接口`
        : "等待按钮门控 POST task 写入 provider ledger 或本地阻断",
      用户下一步: quantProjectionProviderLedgerReady ? "继续回放 P2 三面和 P3 结果" : "先看任务状态；凭据缺失时按本地阻断处理",
      证据: `provider_call_source=${quantProjectionProviderCallSource}`,
      边界: "Tushare 只允许在 POST task / worker 内调用；DeepSeek 只读取安全事实摘要，可成功或安全降级"
    },
    {
      链路节点: "3. P2 三面写回",
      当前状态: quantProjectionSmallDataStageLabel,
      用户下一步: quantProjectionSmallDataNextStep,
      证据: quantProjectionSmallDataWritebackSurfaces,
      边界: quantProjectionSmallDataReadbackContract
    },
    {
      链路节点: "4. P3 可解释结果",
      当前状态: quantProjectionOrdinaryResultSummary,
      用户下一步: quantProjectionOrdinaryResultNext,
      证据: quantProjectionOrdinaryResultEvidence,
      边界: quantProjectionOrdinaryResultBoundary
    },
    {
      链路节点: "5. 结果入口",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      证据: "股票量化推演 / 次日图谱 / 候选池本地入口",
      边界: quantProjectionReplayBoundary
    }
  ];
  const quantProjectionPostConfirmPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_post_confirm_action_rows);
  const quantProjectionPostConfirmActionRows = quantProjectionPostConfirmPacketRows.length ? quantProjectionPostConfirmPacketRows : [
    {
      行动: "1. 看任务编号",
      当前状态: quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId || "等待点击确认按钮",
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "确认 task id 后看 TaskStatusPanel"
        : quantProjectionSubmitError
          ? "先恢复本地后端连接，再重新点击确认"
          : "输入有效代码并点击确认",
      边界: "task id 只来自按钮门控 POST 或 cache packet；输入、搜索、GET cache 不创建 task"
    },
    {
      行动: "2. 看任务进度",
      当前状态: (taskId || quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId)
        ? "TaskStatusPanel 可轮询本地 FastAPI"
        : "等待本地 task id",
      用户下一步: "等待 success 后刷新本地 cache",
      边界: "TaskStatusPanel 只轮询本地任务状态；不调用 Tushare/DeepSeek/GitHub、不写交易动作"
    },
    {
      行动: "3. 刷新本地 cache",
      当前状态: quantProjectionSmallDataReady ? "cache / ledger / packet 可回放" : "等待任务完成后刷新",
      用户下一步: "刷新后看小数据写入位置和结果入口",
      边界: "GET cache 只读回放，不补调 provider/model、不泄露敏感凭据"
    },
    {
      行动: "4. 回放结果",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      边界: "只切换 #factor/#next 锚点，不重新创建 task、不改 strategy action；不改交易策略"
    }
  ];
  const quantProjectionTaskSuccessRefreshRows = [
    {
      回读项: "1. TaskStatusPanel success",
      当前状态: quantProjectionTaskPanelTaskId ? "可轮询本地任务状态" : "等待 task id",
      成功后动作: "调用 refreshQuantProjectionReadback，回读 CandidateRadar cache 和 bootstrap status",
      用户下一步: quantProjectionSmallDataReady ? "继续打开量化推演和次日图谱回放" : "等待 success 后确认 P2 三面是否可回放",
      边界: "TaskStatusPanel 只轮询本地 FastAPI；success 回调不创建第二个 task、不补调 Tushare/DeepSeek"
    },
    {
      回读项: "2. cache / ledger / packet",
      当前状态: quantProjectionSmallDataReady ? "P2 三面已可回放" : "等待本地 cache 刷新后回放",
      成功后动作: "refreshCache() 只读取 GET /api/candidate-radar/cache",
      用户下一步: "看 P2 小数据三面回放和 P3 结果速读",
      边界: "GET cache 只读；不展示 raw log、敏感凭据或 provider error"
    },
    {
      回读项: "3. 结果入口",
      当前状态: quantProjectionReplayDestinationState,
      成功后动作: "结果入口只切换 #factor / #next 本地模块",
      用户下一步: quantProjectionReplayDestinationNextStep,
      边界: "回放链接不重新创建 task、不调用模型、不交易、不改交易策略"
    }
  ];
  const quantProjectionOneScreenPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_one_screen_action_rows).map((row) => ({
    行动: displayText(row["行动"] ?? row.action_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_action, quantProjectionSmallDataNextStep),
    入口: displayText(row["入口"] ?? row.entry),
    边界: displayText(row["边界"] ?? row.boundary, "只读回放本地 cache / ledger / packet；不会从摘要创建 task 或调用模型")
  }));
  const quantProjectionOneScreenActionRows = quantProjectionOneScreenPacketRows.length ? quantProjectionOneScreenPacketRows : [
    {
      行动: "1. 确认",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: quantProjectionCanSubmit ? "点击确认并生成 3.0 量化推演" : "先输入有效股票代码并确认本地后端联通",
      入口: "确认并生成 3.0 量化推演",
      边界: "只有确认按钮可创建 Tushare-first POST task；输入、搜索、GET cache 和 React render 不外联"
    },
    {
      行动: "2. 任务",
      当前状态: (taskId || quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId)
        ? "TaskStatusPanel 可本地轮询"
        : "等待确认按钮返回 task id",
      用户下一步: "看本地任务状态；success 后刷新 cache 回放",
      入口: "TaskStatusPanel",
      边界: "任务状态只轮询本地 FastAPI；不调用 Tushare、DeepSeek、GitHub 或交易路径"
    },
    {
      行动: "3. 写回",
      当前状态: quantProjectionSmallDataStageLabel,
      用户下一步: quantProjectionSmallDataNextStep,
      入口: "cache / call_ledger / packet",
      边界: quantProjectionSmallDataReadbackContract
    },
    {
      行动: "4. 结果",
      当前状态: quantProjectionOrdinaryResultSummary,
      用户下一步: quantProjectionReplayDestinationNextStep,
      入口: "股票量化推演 / 次日图谱",
      边界: "结果只是研究回放；不调用 DeepSeek、不覆盖 strategy action、不生成交易指令"
    }
  ];
  const ordinaryP1ConfirmPathLabel = quantProjectionCanSubmit
    ? `P1 主路径：点击确认创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task；点击确认后提交 Tushare-first 后台链`
    : "P1 主路径：先输入股票代码；输入只做本地校验，确认按钮才创建 Tushare-first task";
  const ordinaryP1ConfirmPathBoundary =
    `P1 主路径只允许确认按钮创建 Tushare-first task；点击确认才创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task；本页不会从输入或渲染创建 Tushare-first task；搜索输入、页面打开、React render、GET cache 和结果链接都不外联。`;
  const ordinaryP1ConfirmPathRows = [
    {
      阶段: "1. 输入股票代码",
      当前状态: quantProjectionInputValidation,
      用户下一步: quantProjectionCanSubmit ? "确认按钮已可用，点击一次即可创建后台链" : "输入 6 位 A 股代码或带 .SZ/.SH/.BJ 后缀",
      边界: "输入只做本地校验；不创建 task、不调用 Tushare/DeepSeek/GitHub"
    },
    {
      阶段: "2. 点击确认按钮",
      当前状态: quantProjectionDisabledReason,
      用户下一步: quantProjectionCanLaunch ? "点击确认并生成 3.0 量化推演" : "等待有效代码和本地后端联通",
      边界: "只有确认按钮创建本地 POST task；DeepSeek 只读解释可安全降级；不交易；只有确认按钮会 POST /api/candidate-radar/quant-projection"
    },
    {
      阶段: "3. 看任务接收",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId ? "看 task id 和 TaskStatusPanel" : "确认后等待本地 task id；失败先回 P0 联通恢复",
      边界: "TaskStatusPanel 只轮询本地 FastAPI；不补调 provider/model、不写交易动作"
    },
    {
      阶段: "4. 回放本地结果",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      边界: "只从 cache / ledger / packet 回放 #factor/#next；不创建第二个 task、不改交易策略"
    }
  ];
  const ordinaryP1ToP3StageRailState = [
    quantProjectionSymbolReady ? "input_ready" : searchSymbol.trim() ? "input_blocked" : "input_waiting",
    quantProjectionSubmitError ? "confirm_failed" : quantProjectionSubmitting ? "confirm_submitting" : quantProjectionCanSubmit ? "confirm_ready" : "confirm_waiting",
    taskReceipt?.ok || quantProjectionPersistedTaskId ? "task_accepted" : "task_waiting",
    quantProjectionSmallDataReady ? "p2_ready" : "p2_waiting",
    quantProjectionInterpretationReady ? "p3_ready" : "p3_waiting"
  ].join(" ");
  const ordinaryP1ToP3StageRailSteps = [
    {
      label: "输入静默",
      state: quantProjectionSymbolReady ? ("done" as const) : searchSymbol.trim() ? ("blocked" as const) : ("waiting" as const),
      detail: quantProjectionInputValidation
    },
    {
      label: "确认按钮",
      state: quantProjectionSubmitError
        ? ("blocked" as const)
        : quantProjectionSubmitting
          ? ("active" as const)
          : taskReceipt?.ok || quantProjectionPersistedTaskId
            ? ("done" as const)
            : quantProjectionCanSubmit
              ? ("active" as const)
              : ("waiting" as const),
      detail: quantProjectionCanSubmit ? "POST task ready" : "等待本地校验"
    },
    {
      label: "任务接收",
      state: quantProjectionSubmitError
        ? ("blocked" as const)
        : quantProjectionSubmitting
          ? ("active" as const)
          : taskReceipt?.ok || quantProjectionPersistedTaskId
            ? ("done" as const)
            : ("waiting" as const),
      detail: taskReceipt?.ok || quantProjectionPersistedTaskId ? "task id 可见" : "等待确认"
    },
    {
      label: "P2 三面",
      state: quantProjectionSmallDataReady ? ("done" as const) : (taskReceipt?.ok || quantProjectionPersistedTaskId) ? ("active" as const) : ("waiting" as const),
      detail: quantProjectionSmallDataReady ? "cache/ledger/packet" : "等待回放"
    },
    {
      label: "P3 速读",
      state: quantProjectionInterpretationReady ? ("done" as const) : quantProjectionSmallDataReady ? ("active" as const) : ("waiting" as const),
      detail: quantProjectionInterpretationReady ? "可解释结果" : "等待本地结果"
    }
  ];
  const quantProjectionConfirmReplayStageRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_confirm_replay_stage_rows).map((row) => ({
    速读项: displayText(row["速读项"] ?? row.stage_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_step),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "GET cache 只读回放；不创建 task、不补调 provider/model")
  }));
  const quantProjectionConfirmOutcomePacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_confirm_outcome_rows).map((row) => ({
    速读项: displayText(row["速读项"] ?? row.outcome_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    用户下一步: displayText(row["用户下一步"] ?? row.next_step),
    入口: displayText(row["入口"] ?? row.entry),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "GET cache 只读回放；不创建 task、不补调 provider/model")
  }));
  const quantProjectionOrdinaryConfirmOutcomeRows = quantProjectionConfirmOutcomePacketRows.length ? quantProjectionConfirmOutcomePacketRows : quantProjectionConfirmReplayStageRows.length ? quantProjectionConfirmReplayStageRows : [
    {
      速读项: "P1/P2 当前阶段",
      当前状态: quantProjectionConfirmReplayStage,
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId
        ? "等 TaskStatusPanel success 后刷新本地 cache"
        : quantProjectionCanSubmit
          ? "点击确认并生成 3.0 量化推演"
          : "先输入有效股票代码",
      边界: "阶段只由本地 task receipt / cache 推导；不创建 task、不补调 provider/model"
    },
    {
      速读项: "确认任务",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: quantProjectionSubmitError
        ? "先恢复本地 FastAPI 连接，再重新点击确认按钮"
        : taskReceipt?.ok || quantProjectionPersistedTaskId
          ? "看任务编号和本地任务状态"
          : "输入有效股票代码后点击确认并生成",
      边界: "只解释确认按钮是否创建本地 POST task；不会从摘要补调 provider/model"
    },
    {
      速读项: "任务编号",
      当前状态: quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId || "等待确认按钮",
      用户下一步: (taskId || quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId)
        ? "TaskStatusPanel 只轮询本地 FastAPI，完成后刷新 cache"
        : "点击确认后等待本地 task id",
      边界: "task id 来自按钮门控 POST 或 cache packet；GET cache 不创建 task"
    },
    {
      速读项: "结果回放",
      当前状态: quantProjectionSmallDataStageLabel,
      用户下一步: quantProjectionSmallDataReady
        ? "打开股票量化推演和次日图谱只读回放"
        : "任务完成后刷新本地 cache，再看 cache / ledger / packet",
      边界: "结果只从 cache / ledger / packet 回放；不交易、不改 strategy action；不交易、不改交易策略"
    }
  ];
  const quantProjectionReadbackIndexRows = [
    {
      回放清单: "确认回执",
      可回放项: Number(counts.search_quant_projection_confirmed_task_receipt_row_count ?? 0),
      当前状态: Number(counts.search_quant_projection_confirmed_task_receipt_row_count ?? 0) ? "可回放确认任务接收回执" : "等待确认任务写入回执",
      只读边界: policy.search_quant_projection_confirmed_task_receipt_rows_are_cache_only === false ? "待复核" : "只读回放",
      边界: "确认回执只从 cache / packet 回放；不创建第二个 task、不补调 Tushare/DeepSeek"
    },
    {
      回放清单: "任务回放",
      可回放项: Number(counts.search_quant_projection_task_readback_row_count ?? 0),
      当前状态: Number(counts.search_quant_projection_task_readback_row_count ?? 0) ? "可回放 task id / safe current_step" : "等待本地 task id 写入 cache",
      只读边界: policy.search_quant_projection_task_readback_rows_are_cache_only === false ? "待复核" : "只读回放",
      边界: "TaskStatusPanel 只轮询本地 FastAPI；GET cache 不创建 task"
    },
    {
      回放清单: "数据接口回放",
      可回放项: Number(counts.search_quant_projection_provider_api_row_count ?? 0),
      当前状态: Number(counts.search_quant_projection_provider_api_row_count ?? 0) ? "可回放 Tushare light API 状态" : "等待 Tushare-first ledger 或本地阻断",
      只读边界: policy.search_quant_projection_provider_api_rows_are_cache_only === false ? "待复核" : "只读回放",
      边界: "数据接口行只读回放 ledger 状态；React render 不调用 provider/model"
    },
    {
      回放清单: "P3 结果速读",
      可回放项: Number(counts.search_quant_projection_interpretation_quick_read_row_count ?? 0),
      当前状态: Number(counts.search_quant_projection_interpretation_quick_read_row_count ?? 0) ? "可回放可读结论 / 来源组成 / 缺口" : "等待小数据写入后生成结果速读",
      只读边界: policy.search_quant_projection_interpretation_quick_read_rows_are_cache_only === false ? "待复核" : "只读回放",
      边界: "结果速读不创建 task、不调用模型、不生成交易动作"
    }
  ];
  const quantProjectionTushareFirstChainRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_tushare_first_chain_rows);
  const quantProjectionConfirmHandoffRows = quantProjectionTushareFirstChainRows.length ? quantProjectionTushareFirstChainRows : [
    {
      步骤: "输入校验",
      触发: "输入框本地校验",
      后台: "不创建任务",
      回放: quantProjectionInputValidation,
      边界: "搜索输入、React render、GET cache 不外联"
    },
    {
      步骤: "点击确认",
      触发: "确认并生成按钮",
      后台: "创建 Tushare-first POST task / worker",
      回放: quantProjectionLatestTaskState,
      边界: "只有用户确认后才进入后台链"
    },
    {
      步骤: "Tushare 写入",
      触发: "后台任务",
      后台: "凭据可用才写 call_ledger / cache / packet",
      回放: quantProjectionProviderModelReplayState,
      边界: "凭据可用才写 provider ledger；Tushare 缺失只写本地阻断，DeepSeek 不编造事实"
    },
    {
      步骤: "结果回放",
      触发: "查看本地结果",
      后台: "不再创建任务",
      回放: "量化推演 / 次日图谱读取 cache / ledger / packet",
      边界: "不交易、不改交易策略"
    }
  ];
  const quantProjectionServerConfirmButtonReadinessRows = rows(
    searchQuantProjectionSmallDataWriteback.ordinary_confirm_button_readiness_rows
  ).map((row) => {
    const readinessKey = String(row.readiness_key ?? "");
    const localStatus =
      readinessKey === "input_local_validation"
        ? quantProjectionInputValidation
        : readinessKey === "confirm_button_post_task_ready"
          ? quantProjectionDisabledReason
          : readinessKey === "task_receipt_readback"
            ? quantProjectionConfirmChainState
            : readinessKey === "cache_replay_after_success"
              ? quantProjectionReplayDestinationState
              : "";
    const localNextStep =
      readinessKey === "input_local_validation"
        ? quantProjectionCanSubmit
          ? "代码已通过本地校验，可以看确认按钮"
          : "修正为 6 位 A 股代码或带 .SZ/.SH/.BJ 后缀"
        : readinessKey === "confirm_button_post_task_ready"
          ? quantProjectionCanLaunch
            ? "点击一次确认并生成 3.0 量化推演"
            : "等待按钮启用，或先恢复本地 FastAPI 连接"
          : readinessKey === "task_receipt_readback"
            ? taskReceipt?.ok || quantProjectionPersistedTaskId
              ? "看 task id 和 TaskStatusPanel"
              : "确认后等待本地 task id；失败先回 P0 联通恢复"
            : readinessKey === "cache_replay_after_success"
              ? quantProjectionReplayDestinationNextStep
              : "";
    return {
      门控项: displayText(row["门控项"] ?? row.readiness_key),
      当前状态: displayText(localStatus || (row["当前状态"] ?? row.status)),
      用户下一步: displayText(localNextStep || (row["用户下一步"] ?? row.next_action)),
      允许动作: displayText(row["允许动作"] ?? row.allowed_action),
      边界: displayText(row["边界"] ?? row.boundary)
    };
  });
  const quantProjectionP1ConfirmGateFallbackRows = [
    {
      门控项: "1. 输入代码",
      当前状态: quantProjectionInputValidation,
      用户下一步: quantProjectionCanSubmit ? "代码已通过本地校验，可以看确认按钮" : "修正为 6 位 A 股代码或带 .SZ/.SH/.BJ 后缀",
      允许动作: "本地校验",
      边界: "输入框不创建 task、不调用 Tushare/DeepSeek/GitHub"
    },
    {
      门控项: "2. 确认按钮",
      当前状态: quantProjectionDisabledReason,
      用户下一步: quantProjectionCanLaunch ? "点击一次确认并生成 3.0 量化推演" : "等待按钮启用，或先恢复本地 FastAPI 连接",
      允许动作: "按钮门控 POST /api/candidate-radar/quant-projection",
      边界: "只有确认按钮可创建 Tushare-first task；DeepSeek 只读解释可安全降级，不交易"
    },
    {
      门控项: "3. 任务接收",
      当前状态: quantProjectionConfirmChainState,
      用户下一步: taskReceipt?.ok || quantProjectionPersistedTaskId ? "看 task id 和 TaskStatusPanel" : "确认后等待本地 task id；失败先回 P0 联通恢复",
      允许动作: "TaskStatusPanel 本地轮询",
      边界: "轮询本地 FastAPI 任务状态；不补调 provider/model，不写交易动作"
    },
    {
      门控项: "4. 回放结果",
      当前状态: quantProjectionReplayDestinationState,
      用户下一步: quantProjectionReplayDestinationNextStep,
      允许动作: "刷新 GET cache 后只读回放",
      边界: "cache / ledger / packet 回放不创建第二个 task，不覆盖 strategy action"
    }
  ];
  const quantProjectionP1ConfirmGateRows = quantProjectionServerConfirmButtonReadinessRows.length
    ? quantProjectionServerConfirmButtonReadinessRows
    : quantProjectionP1ConfirmGateFallbackRows;
  const quantProjectionConfirmTriggerPacketRows = rows(searchQuantProjectionSmallDataWriteback.ordinary_confirm_trigger_boundary_rows).map((row) => ({
    触发点: displayText(row["触发点"] ?? row.trigger_key),
    当前状态: displayText(row["当前状态"] ?? row.status),
    允许动作: displayText(row["允许动作"] ?? row.allowed_action),
    证据: displayText(row["证据"] ?? row.evidence),
    边界: displayText(row["边界"] ?? row.boundary, "输入/GET/render 只读；确认按钮才创建 POST task")
  }));
  const quantProjectionConfirmTriggerBoundaryRows = quantProjectionConfirmTriggerPacketRows.length ? quantProjectionConfirmTriggerPacketRows : [
    {
      触发点: "1. 输入股票代码",
      当前状态: quantProjectionInputValidation,
      允许动作: "本地格式校验",
      证据: "normalizeAshareSymbolInput",
      边界: "输入框只做本地校验；不创建 task、不调用 Tushare/DeepSeek/GitHub"
    },
    {
      触发点: "2. 确认按钮",
      当前状态: quantProjectionConfirmChainState,
      允许动作: "POST /api/candidate-radar/quant-projection",
      证据: quantProjectionAcceptedTaskId || quantProjectionPersistedTaskId || "button_not_clicked",
      边界: "只有确认按钮可创建 Tushare-first POST task；DeepSeek 只读解释可安全降级，不交易"
    },
    {
      触发点: "3. Tushare-first task ledger",
      当前状态: quantProjectionProviderModelReplayState,
      允许动作: "后台任务写 call_ledger / cache / packet",
      证据: `provider_call_source=${quantProjectionProviderCallSource}`,
      边界: "Tushare 只允许在按钮门控 POST task / worker 内调用；GET cache 和 React render 不补调 provider"
    },
    {
      触发点: "4. GET cache 回放",
      当前状态: quantProjectionSmallDataStageLabel,
      允许动作: "只读回放 cache / ledger / packet",
      证据: "GET /api/candidate-radar/cache",
      边界: "GET cache、React render、结果链接只回放本地结果；不创建第二个 task、不调用 provider/model、不改交易策略"
    }
  ];
  const quantProjectionOrdinaryEndToEndRows = [
    {
      步骤: "1. 打开 3.0",
      用户动作: "用一键启动器打开页面；若确认失败，先恢复本地 FastAPI 连接",
      当前状态: quantProjectionSubmitError ? "本地连接需复核" : "页面已进入只读 cache 状态",
      下一步: "查看本地缓存，或继续输入股票代码",
      边界: "FastAPI 启动、页面打开、React render、GET cache 不调用 Tushare/DeepSeek/GitHub"
    },
    {
      步骤: "2. 输入代码",
      用户动作: "输入 002008.SZ 或 002008",
      当前状态: quantProjectionInputValidation,
      下一步: quantProjectionCanSubmit ? "点击确认并生成 3.0 量化推演" : "修正代码后再确认",
      边界: quantProjectionInputBoundaryLabel
    },
    {
      步骤: "3. 点击确认",
      用户动作: "点击确认并生成 3.0 量化推演",
      当前状态: quantProjectionConfirmChainState,
      下一步: taskReceipt?.ok || quantProjectionPersistedTaskId ? "看任务编号和 TaskStatusPanel" : "等待按钮启用，或先恢复本地后端连接",
      边界: "只有确认按钮创建 Tushare-first POST task / worker；DeepSeek 只读解释可安全降级，不交易"
    },
    {
      步骤: "4. 回放结果",
      用户动作: "刷新本地缓存后查看量化推演和次日图谱",
      当前状态: quantProjectionReplayDestinationState,
      下一步: quantProjectionReplayDestinationNextStep,
      边界: "结果只从 cache / ledger / packet 回放；链接不重新创建 task、不改 strategy action；链接不重新创建 task、不改交易策略"
    }
  ];
  const quantProjectionResultLocation =
    "结果位置：股票量化推演页查看缓存结果，次日图谱页复核图谱；两个入口都只读回放";
  const quantProjectionP3ResultSummaryItems = [
    {
      label: "可读结论",
      value: quantProjectionOrdinaryResultSummary,
      tone: quantProjectionInterpretationReady ? "good" as const : "warn" as const
    },
    {
      label: "P3 结果证据",
      value: quantProjectionP3ExplainableResultCheckpointLabel,
      tone: quantProjectionInterpretationReady ? "good" as const : "warn" as const
    },
    {
      label: "数据来源",
      value: quantProjectionOrdinaryResultEvidence,
      tone: quantProjectionProviderLedgerReady ? "good" as const : "warn" as const
    },
    {
      label: "DeepSeek 解释",
      value: quantProjectionDeepSeekVisibleStatus,
      tone: quantProjectionDeepSeekOutputReady ? "good" as const : quantProjectionDeepSeekDegraded ? "warn" as const : "neutral" as const
    },
    {
      label: "下一步",
      value: quantProjectionOrdinaryResultNext
    },
    {
      label: "安全边界",
      value: quantProjectionOrdinaryResultBoundary,
      tone: "good" as const
    }
  ];
  const quantProjectionP3ResultRouteReady = quantProjectionInterpretationReady || quantProjectionSmallDataReady;
  const quantProjectionP3ResultRouteSentence = quantProjectionP3ResultRouteReady
    ? `${quantProjectionProgressWatchSymbol || quantProjectionDisplaySymbol || "当前标的"} P3 结果路标：先看股票量化推演支持/压制，再打开次日图谱，换标的回确认输入区。`
    : "P3 结果路标：确认前先看 P1 按钮；确认后等 P2 三面和 P3 结论回放，再打开量化推演和次日图谱。";
  const quantProjectionP3ResultRouteBoundary =
    "P3 结果路标只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不交易、不改交易策略";
  const quantProjectionP3ResultRouteItems: MetricItem[] = [
    { label: "当前结果", value: quantProjectionInterpretationReady ? quantProjectionOrdinaryResultSummary : quantProjectionProgressWatchReadableStatus, tone: quantProjectionP3ResultRouteReady ? "good" : "warn" },
    { label: "先看哪里", value: quantProjectionInterpretationReady ? "股票量化推演支持/压制" : "任务进度和 P2 三面", tone: quantProjectionP3ResultRouteReady ? "good" : "warn" },
    { label: "图谱", value: quantProjectionInterpretationReplay, tone: quantProjectionInterpretationReady ? "good" : "warn" },
    { label: "换标的", value: "回确认输入区；输入静默，确认按钮才创建 Tushare-first task", tone: "good" },
    { label: "边界", value: quantProjectionP3ResultRouteBoundary, tone: "good" }
  ];
  const candidateRadarStatusLabel = candidateRadarCacheReady
    ? "候选缓存可用"
    : candidateRadarCacheGetReadable
      ? "本地回放可用"
      : "等待候选缓存";
  const candidatePoolCacheDetail = candidateRadarCacheReady
    ? "本地候选缓存可用"
    : candidateRadarCacheGetReadable
      ? `本地回放可用：${String(cache.status)}`
      : "等待本地缓存";
  const candidatePoolSignalDetail = Number(scanCoverage.missing_signal_group_count ?? 0)
    ? `缺少 ${String(scanCoverage.missing_signal_group_count)} 组信号`
    : "信号覆盖完整";
  const candidatePoolDeepResearchDetail =
    deepScanPlan.status === "deep_scan_plan_ready" ? "深研清单已准备" : "等待整理深研清单";
  const empty = !loading && !error && !Object.keys(cache).length;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>下一票雷达</h1>
          <p>先看候选、数据来源、缺少证据和仅供研究边界。</p>
        </div>
        <StatusBadge label={candidateRadarStatusLabel} tone={candidateRadarCacheGetReadable ? "good" : "neutral"} />
      </div>

      <PacketCard title="下一票雷达操作台" subtitle={candidateRadarCompactOperatorSubtitle} status={candidateRadarStatusLabel}>
        <p className="ordinary-status-note" aria-label="candidate radar operator input confirm first sentence">输入确认速读：输入只做本地校验；确认后看最近结果、候选池、量化推演、次日图谱和 ETF/融资风险。</p>
        <div className="actions" aria-label="candidate radar compact operator actions">
          <input
          value={searchSymbol}
          onChange={(event) => {
            updateSearchSymbolInput(event.target.value);
            setQuantProjectionSubmitError("");
          }}
            placeholder="002008.SZ 或 002008"
            aria-label="candidate radar operator symbol input"
            aria-describedby={candidateRadarOperatorInputHelpId}
            title={quantProjectionInputBoundaryLabel}
          />
          <button
            disabled={quantProjectionSubmitDisabled}
            onClick={launchQuantProjection}
            title={quantProjectionSubmitButtonLabel}
            aria-label={quantProjectionSubmitAriaLabel}
            aria-describedby={candidateRadarOperatorSubmitHelpId}
          >{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}</button>
          <button
            onClick={refreshQuantProjectionReadback}
            disabled={loading}
            title="只刷新本地回放；不启动确认流程、不刷新外部数据或模型"
            aria-label="refresh candidate radar compact operator readback"
          >刷新本地回放</button>
          <a href={candidateRadarP0Blocked ? "#desktop" : "#candidate-radar-search-quant-projection"} aria-label="open candidate radar compact primary action">更多搜票状态</a>
          <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from compact radar panel">候选池</a>
          <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from compact radar panel">量化推演</a>
          <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from compact radar panel">次日图谱</a>
        </div>
        <p id={candidateRadarOperatorInputHelpId} className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionInputSessionState)}</p>
        <p id={candidateRadarOperatorSubmitHelpId} className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionSummaryGuidance)}</p>
        <div aria-label="candidate radar operator post confirm one glance result">
          <h3>确认后马上看这里</h3>
          <p className="ordinary-status-note" aria-label="candidate radar operator post confirm one glance sentence" aria-live="polite">{ordinaryUserText(quantProjectionPostConfirmWaitLabel)}</p>
          <MetricGrid items={ordinaryUserMetricItems(candidateRadarOperatorPostConfirmOneGlanceItems)} />
          <div aria-label="candidate radar post confirm data capability card">
            <h3>确认后数据能力</h3>
            <p className="ordinary-status-note" aria-label="candidate radar post confirm data capability sentence" aria-live="polite">{candidateRadarPostConfirmDataCapabilitySentence}</p>
            <MetricGrid items={ordinaryUserMetricItems(candidateRadarPostConfirmDataCapabilityItems)} />
            <details className="developer-audit-details" aria-label="candidate radar post confirm data capability audit details">
              <summary>研究辅助 / 数据能力明细</summary>
              <p className="risk-note">证据血缘：{dataCapabilityEvidenceLedgerLabel}。真实 Tushare 补证仍需授权 POST task + scope hash + payload + call_ledger + failure-mode evidence；普通首屏不创建第二个 task。</p>
            </details>
          </div>
          <div className="actions" aria-label="candidate radar operator post confirm one glance actions">
            <a href="#tasks" title="切换到任务目录；只读本地进度" aria-label="open tasks from operator post confirm one glance">任务状态</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、待补原因和数据凭证" aria-label="open data capability from operator post confirm one glance">数据能力</a>
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from operator post confirm one glance">量化推演</a>
            <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next from operator post confirm one glance">次日图谱</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from operator post confirm one glance">ETF/融资风险</a>
          </div>
          <p className="risk-note">操作台确认后结果条只读本地确认记录、本地缓存、数据记录和结果包；不会创建第二个后台流程，不交易、不改交易策略；链接只切换本地页面或锚点，不刷新外部数据或模型。</p>
        </div>
        <div aria-label="candidate radar operator input confirm first read">
          <h3>输入确认速读</h3>
          <p className="ordinary-status-note">输入股票后先看本地校验和确认按钮；确认后再看最近结果、候选池、量化推演、次日图谱和 ETF/融资风险。</p>
          <MetricGrid items={candidateRadarVisibleNowItems} />
          <div className="actions" aria-label="candidate radar operator input confirm first read links">
            <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from operator first read">确认输入</a>
            <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from operator first read">候选池</a>
            <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from operator first read">量化推演</a>
            <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from operator first read">次日图谱</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from operator first read">ETF/融资风险</a>
          </div>
          <p className="risk-note">操作台速读只读本地页面状态；输入、链接和刷新本地回放不会刷新外部数据或模型、不会启动后台执行、不会交易。</p>
        </div>
        <div aria-label="candidate radar single ticket closed loop">
          <h3>单票闭环</h3>
          <p className="ordinary-status-note" aria-label="candidate radar single ticket closed loop sentence" aria-live="polite">{ordinaryUserText(candidateRadarSingleTicketLoopSentence)}</p>
          <MetricGrid items={ordinaryUserMetricItems(candidateRadarSingleTicketLoopItems)} />
          <div className="actions" aria-label="candidate radar single ticket closed loop actions">
            <a href="#candidate-pool" title="跳到候选池；只读 Top / Watch / Excluded" aria-label="open candidate pool from single ticket loop">候选池</a>
            <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from single ticket loop">确认输入</a>
            <a href="#tasks" title="查看本地任务目录；不创建新任务" aria-label="open tasks from single ticket loop">任务进度</a>
            <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from single ticket loop">看量化推演</a>
            <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next from single ticket loop">看次日图谱</a>
            <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from single ticket loop">ETF/融资风险</a>
          </div>
          <p className="risk-note">单票闭环只把候选、确认、任务、最近结果和三个回放入口串起来；不提交、不重试、不刷新外部数据或模型、不改交易策略；回放入口只切换本地模块或页内锚点，不启动第二个后台流程、不交易。</p>
        </div>
        <div aria-label="candidate radar compact result and group bridge">
          <h3>结果和分组一屏速读</h3>
          <p className="ordinary-status-note">最近结果、Top/Watch/Excluded 理由、来源和缺口先合成一张短卡；只读本地回放，不创建新的后台流程。</p>
          <MetricGrid items={ordinaryUserMetricItems(candidateRadarCompactResultGroupItems)} />
        </div>
        <div aria-label="candidate radar compact lead candidate result">
          <h3>首位候选速读</h3>
          <p className="ordinary-status-note" aria-label="candidate radar compact lead candidate sentence" aria-live="polite">{candidatePoolLeadReviewSentence}</p>
          <MetricGrid items={candidateRadarCompactLeadCandidateItems} />
          <div aria-label="candidate radar compact top watch excluded reasons">
            <h3>分组理由速读</h3>
            <p className="ordinary-status-note">Top 先复核，Watch 只观察，Excluded 是排除或等待；理由不足会显示为缺口，不自动重排候选。</p>
            <MetricGrid items={candidateRadarCompactGroupDecisionItems} />
          </div>
        </div>
        <MetricGrid
          items={ordinaryUserMetricItems([
            { label: "本地联通", value: candidateRadarP0Blocked ? "未接上" : "已接上", tone: candidateRadarP0Blocked ? "bad" : "good" },
            { label: "当前标的", value: quantProjectionDisplaySymbol || "等待输入" },
            { label: "候选分组", value: ordinaryCandidateGroupLabel, tone: ordinaryCandidateTopCount ? "good" : "warn" },
            { label: "来源", value: coarseFineSourceLabel, tone: coarseFineSourceMode === "tushare_backed_sample" ? "good" : "warn" },
            { label: "最近结果", value: quantProjectionP3OrdinaryReadableSentence, tone: quantProjectionP3OrdinaryReadableSentence.includes("等待") ? "warn" : "good" },
            { label: "缺口", value: ordinaryMissingEvidence, tone: ordinaryMissingEvidence.includes("待补") || ordinaryMissingEvidence.includes("阻断") ? "warn" : "good" },
            { label: "退旧雷达", value: ordinaryRetirementReadinessStateLabel, tone: productionStageScopeManifest.production_radar_replacement_complete === true ? "good" : "warn" },
            { label: "页面 QA", value: ordinaryBrowserQaStatusLabel, tone: browserQaReview.local_browser_qa_review_ready === true || browserQaEvidence.candidate_browser_qa_evidence_ready === true ? "good" : "warn" },
            { label: "下一步", value: ordinaryPrimaryActionLabel },
            { label: "边界", value: "候选不是买入指令；不交易", tone: "good" }
          ])}
        />
        <div aria-label="candidate radar compact vertical slice status">
          <h3>当前纵切状态</h3>
          <p className="ordinary-status-note">输入、确认、最近结果、候选池和缺口先给结论；降级或待补会直接显示，不进入买卖动作。</p>
          <MetricGrid items={candidateRadarCompactVerticalSliceItems} />
        </div>
        <p className="risk-note">退旧雷达前还缺什么：{ordinaryRetirementReadinessMainGaps}；页面检查：{ordinaryBrowserQaStatusLabel}。</p>
        <p className="risk-note">{ordinaryCandidateGroupBoundary} 页面打开、输入、GET cache 和 React render 都不会自动外联。</p>
      </PacketCard>

      <PacketCard title="普通用户雷达摘要" subtitle="下一步、来源、缺口、边界和最近可用缓存" status={candidateRadarStatusLabel}>
        <div aria-label="candidate radar ordinary user first summary">
          <h3>一屏确认</h3>
          <p className="risk-note">默认先看现在做什么、输入状态、确认按钮、最近结果、下一步入口和边界；进度、数据记录和补证细节继续收起。</p>
          <p className="risk-note">输入不会创建 task；只有确认按钮创建本地 POST task；只读回放；确认按钮之外不创建 task；不交易、不改交易策略。</p>
          <p className="risk-note">优先读取 POST 失败 envelope 里的 frontend_backend_auto_link ledger；恢复提示只读展示，不自动重试、不创建 task。</p>
          <MetricGrid items={candidateRadarUserFirstItems} />
          <div aria-label="candidate radar visible now app result">
            <h3>打开 app 能看到什么</h3>
            <p className="ordinary-status-note">这张速读只合成当前本地页面状态：候选池、确认按钮、来源层、缺口和可跳转入口；它不启动确认流程、不刷新外部数据或模型、不交易。</p>
            <MetricGrid items={candidateRadarVisibleNowItems} />
            <div className="actions" aria-label="candidate radar visible now app result actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from visible now app result">候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才启动本地确认流程" aria-label="open confirm input from visible now app result">确认输入</a>
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from candidate radar visible now">数据能力</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from visible now app result">ETF/融资风险</a>
            </div>
          </div>
          <div aria-label="candidate radar typed symbol immediate readback">
            <h3>输入股票后先看这里</h3>
            <p className="ordinary-status-note" aria-label="candidate radar typed symbol immediate sentence" aria-live="polite">{candidateRadarTypedSymbolSentence}</p>
            <MetricGrid items={candidateRadarTypedSymbolItems} />
            <div className="actions" aria-label="candidate radar typed symbol immediate actions">
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才启动本地确认流程" aria-label="open confirm input from typed symbol readback">确认输入</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from typed symbol readback">量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from typed symbol readback">次日图谱</a>
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from typed symbol readback">候选池</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar typed symbol immediate rows">
              <summary>查看输入链路</summary>
              <p className="risk-note">这张输入链路只读当前输入、最近确认记录和本地回放；不会启动确认流程、不会刷新外部数据或模型。</p>
              <DataLineageTable rows={candidateRadarTypedSymbolRows} />
            </details>
            <p className="risk-note">输入股票只是本地会话状态；只有确认按钮点击才启动本地确认流程。结果链接只做本地页面跳转，不交易、不改交易策略。</p>
          </div>
          <div aria-label="candidate radar confirm button primary status card">
            <h3>确认按钮现在能不能点</h3>
            <p className="ordinary-status-note" aria-label="candidate radar confirm button primary status sentence" aria-live="polite">{candidateRadarConfirmButtonPrimarySentence}</p>
            <MetricGrid items={candidateRadarConfirmButtonPrimaryItems} />
            <div className="actions" aria-label="candidate radar confirm button primary status links">
              <a href="#candidate-radar-search-quant-projection" title="跳到真正的确认输入区；只有那里的确认按钮会启动本地确认流程" aria-label="open real confirm input from confirm button status">去确认输入区</a>
              <a href="#tasks" title="切换到本地进度；只读本地状态" aria-label="open task status from confirm button status">任务状态</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from confirm button status">量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from confirm button status">次日图谱</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar confirm button primary status rows">
              <summary>查看按钮状态读法</summary>
              <p className="risk-note">这张按钮状态卡只读本地输入校验、按钮禁用原因、进度和本地回放；不会提交表单、不会启动确认流程、不会刷新外部数据或模型。</p>
              <DataLineageTable rows={candidateRadarConfirmButtonPrimaryRows} />
            </details>
            <p className="risk-note">真正会创建本地研究任务的只有确认输入区的确认按钮；本卡片链接只帮助定位，不买卖、不改持仓、不改 strategy action。</p>
          </div>
          <div aria-label="candidate radar post confirm one glance result card">
            <h3>确认后马上看这里</h3>
            <p className="ordinary-status-note" aria-label="candidate radar post confirm one glance result sentence" aria-live="polite">{ordinaryUserText(quantProjectionPostConfirmWaitLabel)}</p>
            <MetricGrid items={ordinaryUserMetricItems(quantProjectionPostConfirmOneScreenItems)} />
            <div className="actions" aria-label="candidate radar post confirm one glance result actions">
              <a href="#tasks" title="切换到任务目录；只读本地进度" aria-label="open task status from post confirm one glance result">任务状态</a>
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from post confirm one glance result">量化推演</a>
              <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next session from post confirm one glance result">次日图谱</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from post confirm one glance result">ETF/融资风险</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；换标的仍需确认按钮" aria-label="return confirm input from post confirm one glance result">换一只票</a>
            </div>
            <p className="risk-note">这张确认后一眼结果卡只读 task receipt、cache、call_ledger 和 packet；链接只切换本地页面或锚点，不创建第二个 task、不调用 Tushare/DeepSeek/GitHub、不交易、不改 strategy action。</p>
          </div>
          <div aria-label="candidate radar one path p1 p2 p3 route">
            <h3>下一票主路径</h3>
            <p className="ordinary-status-note" aria-label="candidate radar one path p1 p2 p3 sentence" aria-live="polite">{candidateRadarOnePathSentence}</p>
            <MetricGrid items={candidateRadarOnePathItems} />
            <div className="actions" aria-label="candidate radar one path p1 p2 p3 links">
              <a href="#candidate-radar-search-quant-projection" title="跳到确认输入区；只有原确认按钮会启动本地确认流程" aria-label="open confirm input from candidate radar one path">确认输入</a>
              <a href="#tasks" title="切换到任务目录；只读本地进度" aria-label="open task status from candidate radar one path">任务状态</a>
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from candidate radar one path">看量化推演</a>
              <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next session from candidate radar one path">看次日图谱</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from candidate radar one path">ETF/融资风险</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar one path p1 p2 p3 rows">
              <summary>查看主路径读法</summary>
              <p className="risk-note">这张路径表只把确认、进度、结果、风险四步串起来；不会启动确认流程、不会刷新外部数据或模型。</p>
              <DataLineageTable rows={candidateRadarOnePathRows} />
            </details>
            <p className="risk-note">下一票主路径只帮助用户按一条线使用本地投研客户端；候选和结果不是买入、卖出、加仓、融资或下单指令，不下单、不改持仓、不改 strategy action。</p>
          </div>
          <div aria-label="candidate radar recent research result card">
            <h3>确认后最近投研结果</h3>
            <p className="ordinary-status-note" aria-label="candidate radar recent research result sentence" aria-live="polite">{candidateRadarRecentResearchResultSentence}</p>
            <MetricGrid items={candidateRadarRecentResearchResultItems} />
            <div className="actions" aria-label="candidate radar recent research result actions">
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from recent research result card">量化推演</a>
              <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next session from recent research result card">次日图谱</a>
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和降级原因" aria-label="open data capability from recent research result card">数据能力</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from recent research result card">ETF/融资风险</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；换标的仍需确认按钮" aria-label="return confirm input from recent research result card">换一只票</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar recent research result rows">
              <summary>查看结果读法</summary>
              <p className="risk-note">这张结果读法只读本地结果记录、降级和缺口；不会启动确认流程、不会刷新外部数据或模型。</p>
              <DataLineageTable rows={candidateRadarRecentResearchResultRows} />
            </details>
            <p className="risk-note">最近投研结果卡只帮助复核来源、缺口和下一步；它不是买卖建议，不下单、不改持仓、不改 strategy action。</p>
          </div>
          <div aria-label="candidate radar lead candidate review card">
            <h3>候选池首位复核</h3>
            <p className="ordinary-status-note" aria-label="candidate radar lead candidate review sentence" aria-live="polite">{candidatePoolLeadReviewSentence}</p>
            <MetricGrid items={candidatePoolLeadReviewItems} />
            <div className="actions" aria-label="candidate radar lead candidate review actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from lead candidate review">候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from lead candidate review">解释单票</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from lead candidate review">量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from lead candidate review">次日图谱</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from lead candidate review">ETF/融资风险</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar lead candidate review rows">
              <summary>查看复核读法</summary>
              <p className="risk-note">这张复核读法只读 candidate_rows / Top-Watch-Excluded 缓存；不会创建 task、不会运行快扫、不会调用 Tushare/DeepSeek/GitHub、不启动 worker。</p>
              <DataLineageTable rows={candidatePoolLeadReviewRows} />
            </details>
            <p className="risk-note">首位候选只是复核顺序，不是推荐买入；理由、来源或缺口不足时按 degraded 显示，不重排、不重算、不改交易策略。</p>
          </div>
          <div aria-label="candidate radar lead candidate handoff card">
            <h3>首位候选怎么继续</h3>
            <p className="ordinary-status-note" aria-label="candidate radar lead candidate handoff sentence" aria-live="polite">{candidatePoolLeadHandoffSentence}</p>
            <MetricGrid items={candidatePoolLeadHandoffItems} />
            <div className="actions" aria-label="candidate radar lead candidate handoff actions">
              <button
                disabled={!candidatePoolLeadCandidateCanPrefill}
                onClick={prefillLeadCandidateIntoConfirmInput}
                title={candidatePoolLeadCandidateCanPrefill ? `把 ${candidatePoolLeadCandidateTicker} 填入确认输入框；不会提交` : "暂无可带入的首位候选"}
                aria-label="prefill lead candidate into confirm input without submit"
              >带入确认框</button>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from lead candidate handoff">解释单票</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from lead candidate handoff">看量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from lead candidate handoff">看次日图谱</a>
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地 packet 缺口" aria-label="open data capability from lead candidate handoff">数据能力</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from lead candidate handoff">ETF/融资风险</a>
            </div>
            <p className="ordinary-status-note" aria-label="candidate radar lead candidate prefill feedback" aria-live="polite">{candidatePoolLeadHandoffPrefillFeedback}</p>
            <details className="developer-audit-details" aria-label="candidate radar lead candidate handoff rows">
              <summary>查看交接读法</summary>
              <p className="risk-note">这张交接卡只读首位候选、本地输入状态和本地结果入口；只有点击“带入确认框”才写入本地输入框，不提交、不快扫、不调用 Tushare/DeepSeek/GitHub、不启动 worker、不交易。</p>
              <DataLineageTable rows={candidatePoolLeadHandoffRows} />
            </details>
            <p className="risk-note">首位候选交接只是把“下一票”变成可复核的当前标的路径；不把候选包装成买入建议，也不证明 LTG-13 production replacement complete。</p>
          </div>
          <div aria-label="candidate radar empty pool primary action card">
            <h3>候选池为空时现在点哪</h3>
            <p className="ordinary-status-note" aria-label="candidate radar empty pool primary action sentence" aria-live="polite">{candidatePoolEmptyStatePrimarySentence}</p>
            <MetricGrid items={candidatePoolEmptyStatePrimaryItems} />
            <div className="actions" aria-label="candidate radar empty pool primary action links">
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from empty candidate pool action">确认输入</a>
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from empty candidate pool action">候选池</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from empty candidate pool action">量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from empty candidate pool action">次日图谱</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar empty pool primary action rows">
              <summary>查看空池读法</summary>
              <p className="risk-note">这张空池动作卡只读 candidate cache、确认输入状态和最近本地回放；不会创建 task、不会快扫、不会调用 Tushare/DeepSeek/GitHub、不启动 worker。</p>
              <DataLineageTable rows={candidatePoolEmptyStatePrimaryRows} />
            </details>
            <p className="risk-note">空候选池不是买入或清仓信号；主动作只是去确认输入区生成本地研究回放，候选池和结果页继续按 degraded 显示缺口。</p>
          </div>
          <div aria-label="candidate radar user route qa latest evidence">
            <h3>本轮路线 QA</h3>
            <p className="ordinary-status-note" aria-label="candidate radar user route qa summary" aria-live="polite">{candidateRadarUserRouteQaSummary}</p>
            <MetricGrid items={candidateRadarUserRouteQaItems} />
            <div className="actions" aria-label="candidate radar user route qa local actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from user route qa evidence">看候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from user route qa evidence">确认输入</a>
              <a href="#audit" title="跳到折叠审计区；只读查看本地 QA 摘要" aria-label="open audit details from user route qa evidence">审计摘要</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar user route qa evidence rows">
              <summary>查看 QA 明细</summary>
              <p className="risk-note">QA 明细只读 `/api/audit/cache` 汇总的 ignored 本地报告；本页不会打开浏览器、不会写截图、不会创建任务。</p>
              <DataLineageTable rows={candidateRadarUserRouteQaRows} />
            </details>
            <p className="risk-note">这张 QA 速读证明普通路线在本机可打开和可输入；它不是 provider/model 证据、不是远端 CI，也不代表旧雷达可以退场。</p>
          </div>
          <div aria-label="candidate radar post confirm next step bridge">
            <h3>确认后看这 3 处</h3>
            <p className="ordinary-status-note" aria-label="candidate radar post confirm next step sentence" aria-live="polite">{candidateRadarPostConfirmNextStepSentence}</p>
            <MetricGrid items={candidateRadarPostConfirmNextStepItems} />
            <div className="actions" aria-label="candidate radar post confirm next step actions">
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor after candidate radar confirm">看量化推演</a>
              <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next session after candidate radar confirm">看次日图谱</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf after candidate radar confirm">看 ETF/融资</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；换标的仍需确认按钮" aria-label="return confirm input after candidate radar confirm bridge">换一只票</a>
            </div>
            {quantProjectionCrossModuleAlignmentRows.length ? (
              <details className="developer-audit-details" aria-label="candidate radar post confirm factor next alignment details">
                <summary>Factor/Next 对齐明细</summary>
                <p className="risk-note">{quantProjectionCrossModuleAlignmentNext}</p>
                <DataLineageTable rows={quantProjectionCrossModuleAlignmentRows} />
              </details>
            ) : null}
            <p className="risk-note">确认后桥接只解释本地回放入口：Factor、Next 和 ETF/融资都只读已有 cache / packet；普通链接不刷新 provider、不调用模型、不写 cache、不交易、不改交易策略。</p>
          </div>
          <div aria-label="candidate radar ordinary vertical slice readback">
            <h3>纵切速读</h3>
            <p className="ordinary-status-note">搜票输入 -&gt; 确认任务 -&gt; 最近结果 -&gt; 候选池 -&gt; 证据缺口按同一条本地链路展示；这张表只读页面状态，不创建 task、不调用 provider/model。</p>
            <DataLineageTable rows={candidateRadarOrdinaryVerticalSliceRows} />
          </div>
          <div aria-label="candidate radar open app shortest path">
            <h3>打开先看这 4 步</h3>
            <p className="ordinary-status-note">候选池、确认输入、最近结果和非买入边界放在同一屏；链接只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek/GitHub。</p>
            <MetricGrid items={candidateRadarOpenNowPathItems} />
            <div className="actions" aria-label="candidate radar open app shortest path actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from open app shortest path">看候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from open app shortest path">确认输入</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open recent factor result from open app shortest path">最近结果</a>
            </div>
          </div>
          <div aria-label="candidate radar ordinary live light evidence factory">
            <h3>轻量实时证据速读</h3>
            <p className="ordinary-status-note">把本地候选缓存、previous-cache diff、active degraded、退旧雷达缺口和页面 QA 合成一条普通用户速读；这里只读 cache，不创建 task、不调用 provider/model。</p>
            <MetricGrid items={ordinaryLiveLightEvidenceFactoryItems} />
            <div aria-label="candidate radar mode layered live light boundaries">
              <h3>运行模式分层</h3>
              <MetricGrid items={ordinaryModeLayeredLiveLightItems} />
            </div>
            <p className="risk-note" title="全池/深研和真实数据覆盖需未来显式 worker/provider task">下一步：{ordinaryLiveLightFactoryNextStep}；候选只用于研究复核；不是买入、卖出或加仓指令。</p>
            <p className="risk-note">分层速读只解释 cache/render、button/task、provider/model、worker/browser 和 production 边界；不会因为页面打开、输入、React render 或本地链接调用 Tushare/DeepSeek/GitHub，也不证明 LTG-13 production replacement complete。</p>
          </div>
          <div aria-label="candidate radar ltg13 next direct evidence quick read">
            <h3>LTG-13 下一条直接证据</h3>
            <p className="ordinary-status-note">当前 LTG-13 只剩搜票真实数据账本和最终推广复核这两类缺口；首屏只显示授权前状态，不自动运行 Tushare、DeepSeek、GitHub 或 worker。</p>
            <MetricGrid items={candidateRadarLtg13NextDirectEvidenceItems} />
            <div className="actions" aria-label="candidate radar ltg13 next direct evidence actions">
              <a href="#candidate-radar-search-quant-projection" title="跳到搜票确认区；输入仍保持静默，确认按钮才创建本地任务" aria-label="open searched symbol confirm from ltg13 next evidence">确认一只股票</a>
              <a href="#candidate-radar-ltg13-data-ledger-audit" title="跳到折叠审计区查看授权条件；不会自动展开或执行" aria-label="open ltg13 data ledger audit from ordinary summary">查看授权条件</a>
              <button type="button" disabled title="需要用户明确授权真实数据账本补证后，才能运行后台补证任务" aria-label="ltg13 data ledger requires explicit authorization">真实数据补证需授权</button>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar ltg13 next direct evidence rows">
              <summary>查看两项缺口</summary>
              <p className="risk-note">缺口明细默认收起；展开后仍只读本地阶段清单，不创建 task、不调用 Tushare/DeepSeek/GitHub、不启动 worker。</p>
              <DataLineageTable rows={candidateRadarLtg13NextDirectEvidenceRows} />
            </details>
            <p className="risk-note">这条速读只把下一条 direct evidence chain 讲清楚：不把本地 receipt、dry-run、execution request、matrix、browser artifact 或 local review 当 production replacement complete。</p>
          </div>
          <div aria-label="candidate radar real data preflight">
            <h3>真实数据补证授权前状态</h3>
            <p className="ordinary-status-note">{candidateRadarRealDataPreflightState}；这张卡只解释为什么现在是禁用/降级，以及授权前必须准备哪些证据。</p>
            <MetricGrid items={candidateRadarRealDataPreflightItems} />
            <div className="actions" aria-label="candidate radar real data preflight local actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from real data preflight">先看候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from real data preflight">确认一只股票</a>
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from real data preflight">看量化推演</a>
              <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next session from real data preflight">看次日图谱</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from real data preflight">看 ETF/融资</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar real data preflight rows">
              <summary>查看授权前检查项</summary>
              <p className="risk-note">检查项默认收起；展开后仍只读本地状态，不创建 task、不调用 Tushare/DeepSeek/GitHub、不启动 worker。</p>
              <DataLineageTable rows={candidateRadarRealDataPreflightRows} />
            </details>
            <p className="risk-note">真实数据补证只会在未来明确授权的 scope-bound provider run 中发生；普通页面打开、输入、GET cache、React render 和本地链接都不会触发。</p>
          </div>
          <div className="actions" aria-label="candidate radar user first actions">
            <a href={candidateRadarP0Blocked ? "#desktop" : "#candidate-radar-search-quant-projection"} aria-label="open candidate radar user first primary action">{ordinaryPrimaryActionLabel}</a>
            <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from candidate radar user first summary">股票量化推演</a>
            <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate radar user first summary">次日图谱</a>
          </div>
          <div aria-label="candidate radar denoised first screen guide">
            <h3>普通首屏去噪</h3>
            <p className="risk-note">先看操作台、一屏确认、搜票确认和候选池；这不是 acceptance report，也不是 provider 审计入口。</p>
            <MetricGrid
              items={[
                { label: "先看", value: "下一票雷达操作台、一屏确认、搜票确认和候选池" },
                { label: "候选池", value: "Top / Watch / Excluded 仍在候选池首位" },
                { label: "确认按钮", value: "只在 P1 搜票确认区创建按钮门控 POST task" },
                { label: "进度", value: "TaskStatusPanel 和刷新本地回放保留；GET cache 只读" },
                { label: "下沉", value: "重复 P1/P2/P3 表、ledger 和补证路线在详情中" },
                { label: "边界", value: "候选不是买入指令；不交易、不改交易策略", tone: "good" }
              ]}
            />
          </div>
          <div aria-label="candidate radar ordinary candidate review compass">
            <h3>候选复核顺序</h3>
            <p className="ordinary-status-note">打开下一票雷达后先按 Top / Watch / Excluded 复核，再决定是否对单票点确认；这张顺序条只读本地候选缓存，不创建 task、不调用 provider/model。</p>
            <MetricGrid items={ordinaryCandidateReviewCompassItems} />
            <div className="actions" aria-label="candidate radar ordinary candidate review compass actions">
              <a href="#candidate-pool" title="跳到候选池；只读本地缓存" aria-label="open candidate pool from candidate review compass">看候选池</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入仍保持静默，确认按钮才创建本地任务" aria-label="open searched symbol confirm from candidate review compass">解释单票</a>
              <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from candidate review compass">量化推演</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar ordinary candidate review compass rows">
              <summary>查看复核顺序明细</summary>
              <p className="risk-note">复核顺序明细默认收起；展开后仍只读本地候选缓存，不启动快扫、不创建 provider/model/worker 任务。</p>
              <DataLineageTable rows={ordinaryCandidateReviewCompassRows} />
            </details>
            <p className="risk-note">候选复核顺序只帮助用户看懂现有缓存：不交易、不下单、不改交易策略，也不声称 LTG-13 已完成。</p>
          </div>
          <div aria-label="candidate radar ordinary group action strip">
            <h3>分组后下一步</h3>
            <p className="ordinary-status-note" aria-label="candidate radar ordinary group action sentence" aria-live="polite">{ordinaryCandidateGroupActionSentence}</p>
            <MetricGrid items={ordinaryCandidateGroupActionItems} />
            <div className="actions" aria-label="candidate radar ordinary group action local links">
              <a href="#candidate-pool" title="回到候选池；只读本地 Top / Watch / Excluded" aria-label="open candidate pool from group action strip">看分组</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open searched symbol confirm from group action strip">解释单票</a>
              <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from group action strip">看量化推演</a>
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限和缺口" aria-label="open data capability from group action strip">数据能力</a>
              <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from group action strip">ETF/融资风险</a>
            </div>
            <details className="developer-audit-details" aria-label="candidate radar ordinary group action rows">
              <summary>查看分组动作读法</summary>
              <p className="risk-note">分组动作明细默认收起；展开后仍只读本地候选缓存，不运行快扫、不创建 task、不调用 Tushare/DeepSeek/GitHub、不启动 worker。</p>
              <DataLineageTable rows={ordinaryCandidateGroupActionRows} />
            </details>
            <p className="risk-note">Top / Watch / Excluded 只决定复核顺序和入口；不会买入、卖出、加仓、加融资、下单或修改 strategy action。</p>
          </div>
          <div aria-label="candidate radar ordinary retirement readiness quick read">
            <h3>退旧雷达前还缺什么</h3>
            <p className="risk-note">下一票雷达候选池可读；退掉旧雷达前还要补全池/深研、真实数据覆盖、浏览器验收和旧雷达退场审查。本速读只读本地阶段清单。</p>
            <MetricGrid items={ordinaryRetirementReadinessItems} />
            {ordinaryRetirementReadinessGapRows.length ? (
              <details className="developer-audit-details" aria-label="candidate radar ordinary retirement readiness row details">
                <summary>查看退场缺口明细</summary>
                <p className="risk-note">缺口行表默认收起，避免普通首屏变成 acceptance report；展开后也只读本地阶段清单，不创建 task。</p>
                <DataLineageTable rows={ordinaryRetirementReadinessGapRows} />
              </details>
            ) : null}
            <p className="risk-note">本区不创建 task、不启动 worker、不调用 Tushare/DeepSeek/GitHub、不交易；本地收据、dry-run 和浏览器手册都不能当最终完成证据。</p>
          </div>
          <div aria-label="candidate radar ordinary browser qa quick read">
            <h3>本地页面 QA 速读</h3>
            <p className="risk-note">普通页直接回放本地 `#candidates` browser QA 状态：是否有 artifact、视口覆盖是否完整、是否还有本地复核阻断；这仍不是 CI、provider 或 worker 验收。</p>
            <MetricGrid items={ordinaryBrowserQaItems} />
            <details className="developer-audit-details" aria-label="candidate radar ordinary browser qa readback rows">
              <summary>查看本地页面 QA 分层</summary>
              <p className="risk-note">这里不打开浏览器、不写 artifact、不创建 POST task；审查按钮仍保留在开发审计区。</p>
              <DataLineageTable rows={ordinaryBrowserQaReadbackRows} />
            </details>
          </div>
        </div>
        <div aria-label="candidate radar coarse fine screening ordinary summary">
          <h3>粗筛/细筛候选分组</h3>
          <p className="ordinary-status-note">先按现有候选顺序看 Top / Watch / Excluded，再看来源、缺口和仅供研究边界；GET cache、搜索输入和页面渲染不补调外部数据或模型。</p>
          <MetricGrid items={ordinaryCoarseFineItems} />
          {(ordinaryCoarseFineGroupRows.length || ordinaryCoarseFineStageRows.length) ? (
            <details className="developer-audit-details" aria-label="candidate radar coarse fine screening row details">
              <summary>查看分组明细</summary>
              <p className="risk-note">Top / Watch / Excluded 的明细行默认收起；普通首屏先保留分组数字、来源、缺口和 no-buy 边界。</p>
              {ordinaryCoarseFineGroupRows.length ? <DataLineageTable rows={ordinaryCoarseFineGroupRows} /> : null}
              {ordinaryCoarseFineStageRows.length ? <DataLineageTable rows={ordinaryCoarseFineStageRows} /> : null}
            </details>
          ) : null}
          <p className="risk-note">这条切片只说明当前候选分组可读；不是最终替代完成：cache-only / local fallback / Tushare-backed sample 会分开显示；不声称旧雷达可以退场。</p>
        </div>
        <details className="developer-audit-details" aria-label="candidate radar ordinary repeated result progress details">
          <summary>Research Assist / Audit Details：结果和进度明细</summary>
          <p className="risk-note">最近 P3、P2/P3 checkpoint 和进度 watch 默认收起；普通首屏先看操作台、确认按钮、TaskStatusPanel 和确认后一屏结果。</p>
          <div aria-label="candidate radar ordinary p3 one minute result">
            <h3>最近搜票 P3 一分钟结果</h3>
            <p className="ordinary-status-note" aria-label="candidate radar summary p3 readable sentence">{quantProjectionP3OrdinaryReadableSentence}</p>
            <MetricGrid items={quantProjectionP3ResultSummaryItems} />
            <div aria-label="candidate radar p3 result route strip">
              <h3>P3 结果路标</h3>
              <p className="ordinary-status-note" aria-label="candidate radar p3 result route sentence" aria-live="polite">{quantProjectionP3ResultRouteSentence}</p>
              <MetricGrid items={quantProjectionP3ResultRouteItems} />
              <div className="actions" aria-label="candidate radar p3 result route actions">
                <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读回放本地结果" aria-label="open factor support suppress from candidate radar p3 result route">股票量化推演</a>
                <a href="#next/next-session-chart" title={quantProjectionReplayBoundary} aria-label="open next chart from candidate radar p3 result route">次日图谱</a>
                <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；换标的仍需确认按钮" aria-label="open confirm input from candidate radar p3 result route">换一只票</a>
              </div>
              <p className="risk-note">{quantProjectionP3ResultRouteBoundary}</p>
            </div>
            <p className="risk-note">这条结果只读最近确认 task 的本地 cache / call_ledger / packet；不创建第二个 task、不调用 Tushare/DeepSeek、不生成买卖动作。</p>
          </div>
          <div aria-label="candidate radar p2 p3 connection checkpoint">
            <h3>P2/P3 接通 checkpoint</h3>
            <p className="ordinary-status-note" aria-label="candidate radar p2 p3 connection sentence" aria-live="polite">{quantProjectionP2P3ConnectionSentence}</p>
            <MetricGrid items={quantProjectionP2P3ConnectionItems} />
            <div className="actions" aria-label="candidate radar p2 p3 connection actions">
              <a href={quantProjectionP2P3ConnectionPrimaryHref} title={quantProjectionP2P3ConnectionActionBoundary} aria-label="open candidate radar p2 p3 primary action">{quantProjectionP2P3ConnectionPrimaryLabel}</a>
              <a href="#factor" title="切换到股票量化推演；只读回放 P2/P3 本地结果" aria-label="open factor from candidate radar p2 p3 checkpoint">股票量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate radar p2 p3 checkpoint">次日图谱</a>
              <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入仍保持静默" aria-label="open confirm input from candidate radar p2 p3 checkpoint">确认或换一只票</a>
            </div>
            <p className="risk-note">这条 checkpoint 只合成最近确认 task 的 P2 三面和 P3 可读结果；如果缺口还在，只显示待回放，不从页面补调 Tushare/DeepSeek。</p>
          </div>
          <div aria-label="candidate radar ordinary visible progress watch">
            <h3>边用边看进度</h3>
            <p className="risk-note">最近任务、当前步骤和回放入口直接显示在普通摘要里；最近任务、当前步骤和回放入口收在普通摘要明细里；这里只读 GET /api/tasks 与 CandidateRadar cache，不创建 task、不补调 Tushare/DeepSeek。</p>
            <MetricGrid items={quantProjectionTaskIndexProgressItems} />
            <div className="actions" aria-label="candidate radar ordinary visible progress actions">
              <button
                onClick={refreshQuantProjectionReadback}
                disabled={loading}
                title="只回读 CandidateRadar cache 和 bootstrap status；不创建 task、不调用 provider/model"
                aria-label="refresh candidate radar visible progress readback"
              >刷新本地回放</button>
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task catalog from candidate radar visible progress">任务目录</a>
              <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from candidate radar visible progress">股票量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate radar visible progress">次日图谱</a>
            </div>
            <p className="risk-note">进度回放只确认 task id、任务步骤、P2/P3 和结果入口；页面打开、搜索输入、React render 和 GET cache 仍不会自动外联。</p>
          </div>
        </details>
        <details className="developer-audit-details" aria-label="candidate radar ordinary task progress details">
          <summary>任务和回放状态</summary>
          <p className="risk-note">任务编号、任务索引、checkpoint 和 P2/P3 回放状态默认收起；需要边用边看进度时再展开。本区只读 GET /api/tasks 与 CandidateRadar cache。</p>
          <div aria-label="candidate radar ordinary usable now strip">
            <h3>现在可用状态</h3>
            <MetricGrid items={quantProjectionUsableNowItems} />
            <p className="risk-note">这条只合成本地 FastAPI、确认按钮、最近任务和 P2/P3 回放状态；不创建 task、不调用 Tushare/DeepSeek、不改交易策略。</p>
          </div>
          <div aria-label="candidate radar local task index progress watch">
            <h3>本地任务进度</h3>
            <MetricGrid items={quantProjectionTaskIndexProgressItems} />
            <div className="actions" aria-label="candidate radar local task index progress actions">
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task catalog from candidate radar progress watch">任务目录</a>
              <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from candidate radar progress watch">股票量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate radar progress watch">次日图谱</a>
            </div>
            <p className="risk-note">边用边看：{quantProjectionProgressWatchNext}；这只来自 GET /api/tasks 和 CandidateRadar cache，不创建第二个 task、不补调 Tushare/DeepSeek、不真实交易。</p>
          </div>
          <div aria-label="candidate radar ordinary progress checkpoint">
            <h3>当前进度 checkpoint</h3>
            <MetricGrid items={quantProjectionOrdinaryProgressCheckpointItems} />
            <div className="actions" aria-label="candidate radar ordinary progress checkpoint actions">
              <a href={quantProjectionOrdinaryProgressCheckpointAnchor} aria-label="open candidate radar ordinary progress checkpoint next step">{quantProjectionOrdinaryProgressCheckpointLabel}</a>
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress from ordinary progress checkpoint">任务进度</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from ordinary progress checkpoint">次日图谱</a>
            </div>
            <p className="risk-note">checkpoint 只汇总当前输入、task id、P2/P3 回放和下一步入口；链接只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek、不改交易策略。</p>
          </div>
        </details>
        <details className="developer-audit-details" aria-label="candidate radar ordinary summary extra details">
          <summary>摘要细节</summary>
          <p className="risk-note">P0/P1/P2 checkpoint、候选来源、评分说明、P1 回放顺序、P2 checkpoint 和结果位置默认收起；普通用户先看上方一屏确认和 P3 结果速读。</p>
          <MetricGrid
            items={[
              { label: "下一步", value: ordinaryNextClick },
              { label: "主下一步", value: ordinaryPrimaryActionLabel },
              { label: "P0 交接", value: candidateRadarP0HandoffLabel, tone: quantProjectionP0Ready ? "good" : "warn" },
              { label: "P1 主路径", value: ordinaryP1ConfirmPathLabel, tone: quantProjectionCanSubmit ? "good" : "warn" },
              { label: "数据链", value: ordinaryTushareSourceLabel },
              { label: "解释状态", value: ordinaryDeepSeekSourceLabel },
              { label: "待补证据", value: ordinaryPendingSourceLabel, tone: ordinaryPendingSourceLabel.includes("待补") ? "warn" : "good" },
              { label: "P2 小数据回放", value: quantProjectionSmallDataStageLabel, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "P2 三面", value: quantProjectionSmallDataWritebackSurfaces, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "任务边界", value: ordinaryTaskBoundary },
              { label: "仅供研究", value: "候选不是买入指令；不真实交易、不下单、不改交易策略", tone: "good" },
              { label: "主下一步边界", value: ordinaryPrimaryActionBoundary, tone: "good" },
              { label: "P1 主路径边界", value: ordinaryP1ConfirmPathBoundary, tone: "good" },
              { label: "候选分组", value: ordinaryCandidateGroupLabel },
              { label: "候选解读", value: ordinaryCandidateReviewOrder },
              { label: "分组边界", value: ordinaryCandidateGroupBoundary, tone: "good" },
              { label: "扫描范围", value: ordinaryScanScopeLabel },
              { label: "候选来源", value: ordinaryCandidateSourceLabel },
              { label: "评分说明", value: ordinaryScoringReasonLabel },
              { label: "可选补证", value: ordinaryOptionalNextClick },
              { label: "本地缓存", value: ordinaryCacheSourceLabel },
              { label: "降级提示", value: ordinaryDegradedSourceLabel, tone: ordinaryDegradedSourceLabel.includes("降级") && !ordinaryDegradedSourceLabel.includes("未标记") ? "warn" : "good" },
              { label: "最近成功回放", value: ordinaryLastCache },
              { label: "结果位置", value: ordinaryRadarResultLocation, tone: "good" },
              { label: "缺少证据", value: ordinaryMissingEvidence, tone: ordinaryMissingEvidence.includes("待补") || ordinaryMissingEvidence.includes("阻断") || ordinaryMissingEvidence.includes("验收") ? "warn" : "good" },
              { label: "阻断/降级", value: ordinaryBlockedState, tone: ordinaryBlockedState.includes("未标记") ? "good" : "warn" },
              { label: "最近可用缓存", value: ordinaryLastCache },
              { label: "P1 Tushare-first", value: quantProjectionTushareFirstState, tone: quantProjectionProviderLedgerReady ? "good" : "warn" },
              { label: "P1 回放顺序", value: quantProjectionReplayOrder, tone: taskReceipt?.ok || quantProjectionProviderLedgerReady ? "good" : "warn" },
              { label: "P1 确认后等待", value: quantProjectionPostConfirmWaitLabel, tone: taskReceipt?.ok || quantProjectionPersistedTaskId || quantProjectionProviderLedgerReady ? "good" : "warn" },
              { label: "P2 checkpoint", value: quantProjectionWritebackCheckpointLabel, tone: quantProjectionWritebackReadableSurfaceCount === quantProjectionWritebackSurfaceCount ? "good" : "warn" },
              { label: "P2 写入边界", value: quantProjectionSmallDataReadbackContract, tone: "good" }
            ]}
          />
        </details>
        <div id="candidate-radar-search-quant-projection" aria-label="candidate radar first screen quant projection confirmation">
          <h3>P1 搜票确认</h3>
          <div className="actions" aria-label="candidate radar first screen quant projection actions">
            <input
              value={searchSymbol}
              onChange={(event) => {
                updateSearchSymbolInput(event.target.value);
                setQuantProjectionSubmitError("");
              }}
              placeholder="002008.SZ 或 002008"
              aria-label="candidate radar first screen quant projection symbol"
              aria-describedby={quantProjectionSummaryInputHelpId}
              title={quantProjectionInputBoundaryLabel}
            />
            <button
              disabled={quantProjectionSubmitDisabled}
              onClick={launchQuantProjection}
              title={quantProjectionSubmitButtonLabel}
              aria-label={quantProjectionSubmitAriaLabel}
              aria-describedby={quantProjectionSummarySubmitHelpId}
            >{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}</button>
            <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from candidate radar first screen confirmation">股票量化推演</a>
            <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session replay from candidate radar first screen confirmation">次日图谱</a>
          </div>
          <p className="ordinary-status-note" aria-live="polite">{quantProjectionConnectionReadyLabel}</p>
          <p className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionSubmitHint)}</p>
          <p className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionConfirmChainState)}</p>
          {quantProjectionSubmitErrorLabel ? <p className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionSubmitErrorLabel)}</p> : null}
          {quantProjectionP0SubmitRecoveryRows.length ? (
            <div aria-label="candidate radar first screen p0 submit failure recovery">
              <h3>P0 恢复提示</h3>
              <p className="risk-note">确认按钮失败后就在这里看本地联通恢复包：check-only 不启动服务，启动器只在用户运行时恢复 FastAPI/Vite；恢复提示只读展示，不自动重试、不创建 task。</p>
              <DataLineageTable rows={quantProjectionP0SubmitRecoveryRows} />
            </div>
          ) : null}
          <div aria-label="candidate radar first screen p1 task contract quick read">
            <h3>确认后会发生什么</h3>
            <p className="risk-note">普通用户不用展开技术明细也能看到：确认后会生成本地结果、结果写回位置、模型解释和交易边界如何隔离；这张速读只读页面状态，不启动第二个后台流程。</p>
            <MetricGrid items={quantProjectionFirstScreenTaskContractItems} />
          </div>
          <div aria-label="candidate radar ordinary tushare first readiness strip">
            <h3>Tushare-first 当前进度</h3>
            <p className="risk-note">这条进度条把“能不能点确认、任务是否接收、Tushare 账本是否回放、下一步看哪里”合成四格；它只读页面状态和本地回放，不展示审计按钮。</p>
            <MetricGrid items={ordinaryUserMetricItems(quantProjectionTushareFirstOrdinaryReadinessItems)} />
          </div>
          {quantProjectionTaskPanelVisible ? (
            <div aria-label="candidate radar first screen task status">
              <p className="ordinary-status-note">本地进度已记录；完成后刷新本地回放，再看量化推演和次日图谱。</p>
              <TaskStatusPanel taskId={quantProjectionTaskPanelTaskId} onSuccess={refreshQuantProjectionReadback} />
              <details className="developer-audit-details" aria-label="candidate radar first screen task receipt details">
                <summary>查看任务回执</summary>
                <p className="risk-note">普通用户先看上方一句话进度；完整 POST task receipt 默认收起，只作为排查本地任务接收和安全请求摘要的审计材料。</p>
                <div aria-label="quant projection task success refresh checklist">
                  <h3>任务成功后自动回读</h3>
                  <p className="risk-note">TaskStatusPanel success 后调用 refreshQuantProjectionReadback：只回读 CandidateRadar cache 和 bootstrap status；再让用户看 P2 三面与 P3 结果入口；不会创建第二个 task。</p>
                  <DataLineageTable rows={quantProjectionTaskSuccessRefreshRows} />
                </div>
                <TaskLaunchReceipt receipt={taskReceipt} />
              </details>
            </div>
          ) : null}
          {quantProjectionTaskPanelStaleNotice ? (
            <p className="ordinary-status-note" aria-live="polite">{ordinaryUserText(quantProjectionTaskPanelStaleNotice)}</p>
          ) : null}
          <div aria-label="candidate radar post confirm one screen outcome">
            <h3>确认后一屏结果</h3>
            <p className="risk-note">点击确认后先看这条结果：任务是否接收、P2 三面是否回放、P3 结论是否可读和下一步入口都在一屏内；这条结果条只读本地 task receipt 与 cache / ledger / packet，不创建第二个 task；只调用 GET cache / bootstrap status；不会创建第二个 task、不补调 Tushare/DeepSeek、不写交易动作。</p>
            {quantProjectionBackendPostConfirmOneGlanceItems.length ? (
              <details className="developer-audit-details" aria-label="candidate radar backend post confirm one glance">
                <summary>查看同源回放</summary>
                <p className="risk-note">优先读取后端 cache packet 的 search_quant_projection_post_confirm_one_glance_items：任务编号、P2、P3、DeepSeek 和安全边界同源回放；这张状态格只读本地 cache，不创建 task。</p>
                <MetricGrid items={quantProjectionBackendPostConfirmOneGlanceItems} />
              </details>
            ) : null}
            <MetricGrid items={quantProjectionPostConfirmOneScreenItems} />
            <MetricGrid items={quantProjectionResultLineageItems} />
            <p className="risk-note">结果版本把本次 task、Tushare 事实包、provider 账本、输出包和模型账本绑在一起；旧任务迟到只能保留为历史回放，不能覆盖当前标的。</p>
            <details className="developer-audit-details" aria-label="candidate radar post confirm backend replay contract">
              <summary>查看回放顺序</summary>
              <p className="risk-note">这里展示确认后的回放顺序：先看任务编号和状态，再看本地 cache、三面回放、量化推演和次日图谱；这张表只读，不创建 task。</p>
              <DataLineageTable rows={quantProjectionPostConfirmReplayContractRows} />
            </details>
            <div className="actions" aria-label="candidate radar post confirm local replay actions">
              <button
                onClick={refreshQuantProjectionReadback}
                disabled={loading}
                title="只回读 CandidateRadar cache 和 bootstrap status；不创建 task、不调用 provider/model"
                aria-label="refresh candidate radar local replay after p1 confirm"
              >刷新本地回放</button>
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress after p1 confirm">任务进度</a>
              <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay after p1 confirm">量化推演</a>
              <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session replay after p1 confirm">次日图谱</a>
            </div>
            <p className="risk-note">刷新本地回放只读取本地缓存和启动状态，帮助确认结果是否已可读；不会启动第二个后台流程、不补调外部数据或模型解释、不写交易动作。</p>
          </div>
          <details className="developer-audit-details" aria-label="candidate radar first screen p1 chain details">
            <summary>查看确认后清单</summary>
            <p className="risk-note">普通首屏只保留确认按钮、任务状态和一屏结果；按钮路由、回放清单和链路排障默认收起。</p>
            <div aria-label="candidate radar p1 confirm actual route">
              <h3>确认按钮去向</h3>
              <p className="risk-note">这张表只说明当前按钮会走哪条本地后端链路；输入和页面渲染仍保持静默。</p>
              <DataLineageTable rows={quantProjectionConfirmRouteRows} />
            </div>
            <div aria-label="candidate radar first screen post confirm readback guide">
              <h3>确认后看什么</h3>
              <p className="risk-note">点击确认后按这张清单走：先看任务编号，再看任务进度，success 后刷新本地 cache，最后回放量化推演和次日图谱；这张清单只读页面状态，不创建第二个 task。</p>
              <DataLineageTable rows={quantProjectionPostConfirmActionRows} />
            </div>
          </details>
        </div>
        <details className="developer-audit-details" aria-label="candidate radar denoised p1 p3 details">
          <summary>Research Assist / Audit Details：P1/P2/P3 回放明细</summary>
          <p className="risk-note">普通首屏保留确认按钮、TaskStatusPanel、刷新本地回放和候选池；重复 P1/P2/P3 表默认收起，避免打开 #candidates 时像 acceptance report。</p>
        <div aria-label="candidate radar p1 direct confirmation handoff">
          <h3>P1 直接确认入口</h3>
          <p className="risk-note">先确认本地 FastAPI 已接上，然后跳到搜票确认区输入代码；这个入口只做本地锚点跳转，输入仍然静默，只有确认按钮会创建 Tushare-first POST task。</p>
          <div className="actions" aria-label="candidate radar p1 direct confirmation actions">
            <a
              href={candidateRadarP0Blocked ? "#desktop" : "#candidate-radar-search-quant-projection"}
              aria-label="open p1 direct confirmation from radar first screen"
            >{ordinaryPrimaryActionLabel}</a>
            <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress from candidate radar p1 handoff">查看任务进度</a>
          </div>
        </div>
        <div aria-label="candidate radar p2 three surface quick status">
          <h3>P2 三面速读</h3>
          <p className="risk-note">确认按钮完成后先看这里：cache、call_ledger、packet 是否进入本地回放；本速读只读取现有 cache，不创建 task、不补调 Tushare/DeepSeek。</p>
          <MetricGrid
            items={[
              { label: "三面状态", value: quantProjectionSmallDataStageLabel, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "三面组成", value: quantProjectionSmallDataWritebackSurfaces, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "完整度", value: quantProjectionWritebackCheckpointLabel, tone: quantProjectionWritebackReadableSurfaceCount === quantProjectionWritebackSurfaceCount ? "good" : "warn" },
              { label: "P2 写入证据", value: quantProjectionP2ThreeSurfaceCheckpointLabel, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "下一步", value: quantProjectionSmallDataNextStep },
              { label: "边界", value: quantProjectionSmallDataReadbackContract, tone: "good" }
            ]}
          />
          <div aria-label="candidate radar p2 first screen three surface rail">
            <p className="risk-note">cache、call_ledger、packet 三面状态直接在首屏显示；这条状态轨只读本地回放，不创建 task、不补调 provider/model。</p>
            <StateClarityRail
              label="candidate radar p2 first screen three surface rail"
              state={quantProjectionP2WritebackRailState}
              steps={quantProjectionP2WritebackRailSteps}
            />
          </div>
          <div className="actions" aria-label="candidate radar p2 three surface local replay actions">
            <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress from p2 three surface status">查看任务进度</a>
            <a href="#factor" title="切换到股票量化推演；只读回放 cache / ledger / packet" aria-label="open factor replay from p2 three surface status">查看量化推演</a>
            <a href="#next" title="切换到次日图谱；只读回放本地 next-session cache" aria-label="open next session replay from p2 three surface status">查看次日图谱</a>
          </div>
          <p className="risk-note">P2 三面入口只切换本地页面；不会创建第二个 task、不补调 Tushare/DeepSeek、不写 cache，也不改 strategy action。</p>
        </div>
        <div aria-label="candidate radar p3 first screen result quick read">
          <h3>P3 结果首屏速读</h3>
          <p className="risk-note">P2 三面之后直接看这里：可读结论、来源、下一步和安全边界都来自本地 cache / ledger / packet；本速读不创建 task、不调用 DeepSeek、不生成交易动作。</p>
          <p className="ordinary-status-note" aria-label="candidate radar p3 ordinary readable sentence">{quantProjectionP3OrdinaryReadableSentence}</p>
          <div className="actions" aria-label="candidate radar p3 first screen local result actions">
            <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from p3 first screen result">量化推演</a>
            <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session replay from p3 first screen result">次日图谱</a>
            <a href="#candidate-pool" title="跳回候选池；只读回看本地候选缓存" aria-label="return candidate pool from p3 first screen result">候选池</a>
          </div>
          <p className="risk-note">P3 结果入口只切换本地页面或锚点；不会创建 task、不调用 Tushare/DeepSeek、不写 cache，也不改 strategy action。</p>
          <div aria-label="candidate radar p3 one minute decision brief">
            <h3>P3 一分钟决策速读</h3>
            <p className="risk-note">优先读取服务端 ordinary_result_decision_brief_rows：先看结论、再看来源、最后看下一步和边界；这张表只读本地证据，不创建 task。</p>
            <DataLineageTable rows={quantProjectionP3DecisionBriefRows} />
          </div>
          <MetricGrid items={quantProjectionP3ResultSummaryItems} />
          <p className="risk-note">首屏直接回放服务端 ordinary_result_quick_read_rows：现在能读什么、结果从哪里来、还缺什么都只来自本地 cache / ledger / packet。</p>
          <DataLineageTable rows={quantProjectionOrdinaryResultQuickRows} />
        </div>
        </details>
        <details className="developer-audit-details" aria-label="candidate radar ordinary p0 local connection diagnostics">
          <summary>查看本地联通</summary>
          <p className="risk-note">首页已经提供本地 FastAPI 接线速读；普通主线默认收起 P0 联通表，需要排查按钮不可用或启动异常时再展开。</p>
          <div aria-label="candidate radar ordinary p0 frontend backend readiness">
            <h3>P0 前后端联通闸门</h3>
            <p className="risk-note">普通用户先确认本地 FastAPI、bootstrap runtime-mode、desktop preflight 和候选 cache 都能只读回放；P0 未通过时不要进入 P1 确认按钮。</p>
            <DataLineageTable rows={candidateRadarP0AutoLinkRows} />
          </div>
          <div aria-label="candidate radar p0 to p1 preflight handoff">
            <h3>P0 到 P1 交接回读</h3>
            <p className="risk-note">优先读取 desktop preflight 的 p0_to_p1_ordinary_handoff_rows：四段 ready 后只切到搜票量化推演卡；输入保持静默，确认按钮才创建 Tushare-first POST task。</p>
            <DataLineageTable rows={candidateRadarP0HandoffRows} />
          </div>
        </details>
        <p id={quantProjectionSummaryInputHelpId} className="risk-note" aria-live="polite">{quantProjectionInputSessionState}</p>
        <p id={quantProjectionSummarySubmitHelpId} className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionSummaryGuidance)}</p>
        {quantProjectionSubmitErrorLabel ? <p className="risk-note" aria-live="polite">{ordinaryUserText(quantProjectionSubmitErrorLabel)}</p> : null}
        {quantProjectionP0SubmitRecoveryRows.length ? (
          <div aria-label="candidate radar p0 submit failure recovery">
            <h3>确认失败恢复</h3>
            <p className="risk-note">先做本地联通检查，再用一键启动恢复四段 ready。恢复提示只读展示，不自动重试、不启动后台流程。</p>
            <DataLineageTable rows={quantProjectionP0SubmitRecoveryRows} />
          </div>
        ) : null}
        <details className="developer-audit-details" aria-label="candidate radar ordinary expanded p1 p3 readback details">
          <summary>更多回放明细</summary>
          <p className="risk-note">普通主视图保留 P1 确认、任务状态、P2 三面速读和 P3 首屏结果；重复的阶段轨、恢复表、回放索引和 checkpoint 默认收起。</p>
        <div aria-label="candidate radar ordinary p1 to p3 stage rail">
          <h3>P1 到 P3 阶段速览</h3>
          <p className="risk-note">这条状态轨只读本地输入、task receipt 和 cache 回放：输入保持静默，只有确认按钮创建 Tushare-first POST task，P2/P3 只回放本地结果。</p>
          <StateClarityRail
            label="candidate radar ordinary p1 to p3 stage rail"
            state={ordinaryP1ToP3StageRailState}
            steps={ordinaryP1ToP3StageRailSteps}
          />
        </div>
        <div aria-label="candidate radar ordinary one screen actions">
          <h3>一屏行动摘要</h3>
          <p className="risk-note">优先读取服务端 ordinary_one_screen_action_rows：确认、任务、写回、结果合成一张普通用户表；只读回放本地状态，不从摘要创建 task。</p>
          <DataLineageTable rows={quantProjectionOneScreenActionRows} />
        </div>
        <div aria-label="quant projection submit recovery quick read">
          <h3>P1 确认失败恢复</h3>
          <p className="risk-note">确认按钮失败、服务端凭据缺失或任务已接收但未回放时，先看这张表；它只读页面状态和 cache，不自动重试、不创建第二个 task。</p>
          <DataLineageTable rows={quantProjectionSubmitRecoveryRows} />
        </div>
        <div aria-label="quant projection ordinary confirm outcome quick read">
          <h3>P1 确认结果速读</h3>
          <p className="risk-note">优先读取服务端 ordinary_confirm_outcome_rows：点击确认后先看任务是否接收、P2 三面是否回放、P3 入口是否可读；这张速读表不创建第二个任务。</p>
          <DataLineageTable rows={quantProjectionOrdinaryConfirmOutcomeRows} />
        </div>
        <div aria-label="candidate radar p1 tushare first chain quick read">
          <h3>P1 Tushare-first 链路速读</h3>
          <p className="risk-note">优先读取服务端 ordinary_tushare_first_chain_rows：输入只做本地校验，确认按钮才创建 Tushare-first POST task，回放只读 cache / ledger / packet。</p>
          <DataLineageTable rows={quantProjectionConfirmHandoffRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 p3 replay checklist">
          <h3>P2/P3 回放清单</h3>
          <p className="risk-note">确认后先看这张只读索引：确认回执、任务回放、数据接口和 P3 结果速读都来自本地 cache / ledger / packet；不会创建 task、不会补调 Tushare/DeepSeek。</p>
          <DataLineageTable rows={quantProjectionReadbackIndexRows} />
        </div>
        <details className="developer-audit-details" aria-label="candidate radar ordinary p1 p2 detail readback">
          <summary>查看 P1/P2 回放明细</summary>
          <p className="risk-note">一屏行动摘要已经覆盖普通下一步；确认链路、P1 路径和 P2 三面核对默认收起，需要排查时再展开。</p>
        <div aria-label="candidate radar ordinary confirmed chain quick read">
          <h3>确认后链路速读</h3>
          <p className="risk-note">普通用户先看这张确认后链路速读：确认按钮、Tushare-first、P2 三面、P3 结果入口按同一条本地链路回放。</p>
          <DataLineageTable rows={quantProjectionConfirmedChainQuickRows} />
        </div>
        <div aria-label="candidate radar ordinary p1 confirm path">
          <h3>P1 普通确认路径</h3>
          <p className="risk-note">普通用户先看这条 P1 路径：输入只做本地校验，确认按钮才创建 Tushare-first 后台任务，随后只读回放 cache / ledger / packet。</p>
          <DataLineageTable rows={ordinaryP1ConfirmPathRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 writeback rail">
          <h3>P2 三面状态轨</h3>
          <p className="risk-note">先扫 cache、call_ledger、packet 三面是否可读；这条状态轨只读本地回放，不展示接口级 raw log，不创建 task、不补调 Tushare/DeepSeek。</p>
          <StateClarityRail
            label="candidate radar ordinary p2 writeback rail"
            state={quantProjectionP2WritebackRailState}
            steps={quantProjectionP2WritebackRailSteps}
          />
        </div>
        <div aria-label="candidate radar ordinary p2 writeback surfaces">
          <h3>P2 小数据三面回放</h3>
          <p className="risk-note">普通用户确认后看这张表：cache、call_ledger、packet 三面是否可回放；它只读取本地 cache，不创建 task、不补调 Tushare/DeepSeek。</p>
          <DataLineageTable rows={quantProjectionWritebackSurfaceRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 writeback integrity">
          <h3>P2 三面完整性检查</h3>
          <p className="risk-note">普通用户再看这张完整性表：cache、call_ledger、packet 是否齐备；它优先读取服务端 ordinary_writeback_integrity_rows，只做本地回放。</p>
          <DataLineageTable rows={quantProjectionWritebackIntegrityRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 writeback receipt">
          <h3>P2 三面回放凭证</h3>
          <p className="risk-note">需要排查时看这张凭证：cache、call_ledger、packet 三面是否由本地回放读出；它优先读取服务端 ordinary_writeback_receipt_rows，不创建 task、不补调 Tushare/DeepSeek。</p>
          <DataLineageTable rows={quantProjectionP2WritebackReceiptRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 writeback recovery">
          <h3>P2 阻断恢复速读</h3>
          <p className="risk-note">如果 Tushare-first 没有回放，先看这张表区分任务等待、服务端凭据阻断和 DeepSeek 安全降级；它只读本地 cache，不创建任务。</p>
          <DataLineageTable rows={quantProjectionWritebackRecoveryDisplayRows} />
        </div>
        <div aria-label="candidate radar ordinary p2 post confirm cache handoff">
          <h3>P2 确认后缓存回放交接</h3>
          <p className="risk-note">点击确认后先看 task id 和 TaskStatusPanel；success 后刷新本地 cache，再读 cache、call_ledger、packet 三面。</p>
          <DataLineageTable rows={quantProjectionPostConfirmActionRows} />
        </div>
        </details>
        <div aria-label="candidate radar ordinary p3 result summary strip">
          <MetricGrid items={quantProjectionP3ResultSummaryItems} />
        </div>
        <div aria-label="candidate radar ordinary p3 explainable result quick read">
          <h3>P3 可解释结果速读</h3>
          <p className="risk-note">普通用户确认后直接看这张 P3 表：可读结论、来源组成、回放来源和待补证据都来自本地 cache / ledger / packet；不会从速读表创建 task 或调用模型。</p>
          <DataLineageTable rows={quantProjectionOrdinaryResultQuickRows} />
        </div>
        <div aria-label="candidate radar ordinary p3 result checkpoint">
          <h3>P3 结果检查点</h3>
          <p className="risk-note">这张检查点表把可读结论、来源状态、待补缺口和安全字段合成普通用户可读口径；它只读本地 result checkpoint，不创建 task、不调用模型。</p>
          <DataLineageTable rows={quantProjectionOrdinaryResultCheckpointRows} />
        </div>
        <div aria-label="candidate radar ordinary p3 result handoff index">
          <h3>P3 结果入口索引</h3>
          <p className="risk-note">普通用户按这张索引回放可读结论、量化推演、次日图谱和候选池；它只读取服务端 ordinary_result_handoff_rows，不创建 task、不补调模型。</p>
          <DataLineageTable rows={quantProjectionOrdinaryResultHandoffRows} />
        </div>
        </details>
        <div className="actions" aria-label="candidate radar primary next action">
          {candidateRadarP0Blocked ? (
            <a href="#desktop" aria-label="open p0 desktop preflight from radar summary">{ordinaryPrimaryActionLabel}</a>
          ) : (
            <a href="#candidate-radar-search-quant-projection" aria-label="jump to searched symbol confirmation from radar summary">{ordinaryPrimaryActionLabel}</a>
          )}
        </div>
        <details className="developer-audit-details" aria-label="candidate radar optional local actions details">
          <summary>可选本地操作</summary>
          <p className="risk-note">主路径已在上方 P1 搜票确认和边用边看进度里；这里保留缓存刷新、本地快扫和重复确认入口，默认收起，避免普通用户把它当成第二条主流程。</p>
          <div id="candidate-radar-summary-actions" className="actions" aria-label="candidate radar next user actions">
            <button onClick={refreshCache}>查看本地缓存</button>
            {Number(counts.candidate_count ?? 0) ? <button onClick={launchQuickScan}>运行本地快扫</button> : null}
            <input
              value={searchSymbol}
              onChange={(event) => {
                updateSearchSymbolInput(event.target.value);
                setQuantProjectionSubmitError("");
              }}
              placeholder="002008.SZ 或 002008"
              aria-label="radar summary quant projection symbol"
              aria-describedby={quantProjectionSummaryInputHelpId}
              title={quantProjectionInputBoundaryLabel}
            />
            <button
              disabled={quantProjectionSubmitDisabled}
              onClick={launchQuantProjection}
              title={quantProjectionSubmitButtonLabel}
              aria-label={quantProjectionSubmitAriaLabel}
              aria-describedby={quantProjectionSummarySubmitHelpId}
            >{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}</button>
            <a href="#factor" aria-label="open stock quant projection result">查看量化推演结果</a>
            <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session map from candidate radar p1 replay">查看次日图谱</a>
          </div>
        </details>
        <p className="risk-note">{ordinaryRadarResultLocation}</p>
        <p className="risk-note">候选池按 Top / Watch / Excluded 分组帮助复核优先级；分组结果不是买卖建议，也不会修改交易策略。</p>
        <p className="risk-note">摘要按钮只读取本地 cache 或创建按钮门控 POST task；输入代码不会创建任务，也不会在 React 渲染中直连 Tushare、DeepSeek 或 GitHub。</p>
        <p className="risk-note">生成任务完成后，去 <a href="#factor">股票量化推演</a> 查看本地缓存结果；该链接只切换页面，不额外刷新外部数据或模型。</p>
        <p className="risk-note">{quantProjectionResultLocation}</p>
        <p className="risk-note">普通用户无需先打开工程审计；默认先看候选、确认结果和本地回放。</p>
        <details className="developer-audit-details" aria-label="candidate radar ordinary audit shortcuts">
          <summary>高级诊断入口</summary>
          <p className="risk-note">工程审计明细继续默认收起；完整 call ledger、release gate 和配置状态下沉在 <a href="#audit">调用审计</a> / <a href="#settings">配置健康</a>。</p>
        </details>
      </PacketCard>

      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无下一票雷达本地缓存"
        emptyDetail="雷达页只读取本地候选缓存；不会在页面打开或 React 渲染中自动扫描全市场。"
      />

      <div className="grid radar-result-cluster" data-radar-state={radarMotionState}>
        <div id="candidate-pool">
          <PacketCard title="下一票候选池" subtitle="只读展示本地候选缓存；页面打开不会自动全市场扫描" status={candidateRadarStatusLabel}>
            <div aria-label="candidate pool first screen top watch excluded source gap">
              <h3>候选池一屏速读</h3>
              <p className="ordinary-status-note">先看 Top / Watch / Excluded、来源、缺口和评分理由；这张速读只读本地候选缓存，不创建 task、不调用 Tushare/DeepSeek/GitHub。</p>
              <div aria-label="candidate pool plain result conclusion">
                <h3>普通结论</h3>
                <p className="ordinary-status-note" aria-label="candidate pool plain result conclusion text" aria-live="polite">{candidatePoolPlainConclusionText}</p>
                <MetricGrid items={candidatePoolPlainConclusionItems} />
              </div>
              <div aria-label="candidate pool current result card">
                <h3>当前候选怎么用</h3>
                <p className="ordinary-status-note" aria-label="candidate pool current result sentence" aria-live="polite">{candidatePoolCurrentResultSentence}</p>
                <MetricGrid items={candidatePoolCurrentResultItems} />
                <div className="actions" aria-label="candidate pool current result actions">
                  <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="explain lead candidate from current result card">解释单票</a>
                  <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from current result card">量化推演</a>
                  <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from current result card">次日图谱</a>
                  <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from current result card">ETF/融资风险</a>
                </div>
                <p className="risk-note">这张结果卡只读候选池当前缓存和本地来源状态；链接只切换本地页面，不刷新外部数据、不创建新任务、不交易、不改策略。</p>
              </div>
              <MetricGrid items={candidatePoolFirstScreenItems} />
              <div className="actions" aria-label="candidate pool first screen actions">
                <a href="#candidate-radar-search-quant-projection" title="回到确认输入区；输入静默，确认按钮才创建本地任务" aria-label="open confirm input from candidate pool first screen">解释单票</a>
                <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from candidate pool first screen">量化推演</a>
                <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照，不生成加融资指令" aria-label="open margin etf risk budget from candidate pool first screen">ETF/融资风险</a>
                <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate pool first screen">次日图谱</a>
              </div>
              <div aria-label="candidate pool top watch excluded direct actions">
                <h3>按分组直接下一步</h3>
                <p className="ordinary-status-note">Top 先解释单票，Watch 只观察触发条件，Excluded 先看排除原因；这些入口只切换本地页面，不创建任务。</p>
                <MetricGrid items={candidatePoolGroupActionItems} />
                <div className="actions" aria-label="candidate pool top watch excluded direct action links">
                  <a href="#candidate-radar-search-quant-projection" title="Top 候选需要解释时回确认输入区；输入静默，确认按钮才创建本地任务" aria-label="explain top candidate from candidate pool group actions">解释 Top</a>
                  <a href="#candidate-pool" title="Watch 继续留在候选池观察触发条件、来源和缺口" aria-label="watch candidates stay in candidate pool group actions">观察 Watch</a>
                  <a href="#candidate-pool" title="Excluded 继续留在候选池查看排除原因；不删除证据、不创建交易动作" aria-label="review excluded candidates in candidate pool group actions">看 Excluded</a>
                  <a href="#factor" title="切换到股票量化推演；只读本地结果" aria-label="open factor from candidate pool group actions">看量化推演</a>
                  <a href="#next" title={quantProjectionReplayBoundary} aria-label="open next session from candidate pool group actions">看次日图谱</a>
                  <a href="#marginEtf" title="切换到 ETF / 融资风险预算；只读本地快照" aria-label="open margin etf from candidate pool group actions">ETF/融资风险</a>
                </div>
                <p className="risk-note">分组动作只决定复核入口；不会买入、卖出、加仓、加融资、下单或修改 strategy action。</p>
              </div>
            </div>
            <p>{String(cache.summary ?? "候选雷达本地缓存只读展示。")}</p>
            <p>{String(cache.manual_required_text ?? "页面打开不会自动全市场扫描。")}</p>
            <p>候选分组：{ordinaryCandidateGroupLabel}；{ordinaryScanScopeLabel}；{ordinaryCandidateSourceLabel}。</p>
            <p>{ordinaryCandidateGroupBoundary}</p>
            <p>候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。</p>
            <StateClarityRail
              label="候选池状态"
              state={radarMotionState}
              steps={[
                { label: "本地缓存", state: candidateRadarCacheGetReadable ? "done" : "waiting", detail: candidatePoolCacheDetail },
                { label: "信号覆盖", state: Number(scanCoverage.missing_signal_group_count ?? 0) ? "blocked" : "done", detail: candidatePoolSignalDetail },
                { label: "深研清单", state: deepScanPlan.status === "deep_scan_plan_ready" ? "done" : "waiting", detail: candidatePoolDeepResearchDetail },
                { label: "交易边界", state: cache.does_not_execute_trades === false ? "blocked" : "done", detail: "安全" }
              ]}
            />
          </PacketCard>
        </div>

        <div id="factor" aria-label="quant projection factor replay anchor">
        <PacketCard title="搜票量化推演" subtitle="输入代码并确认后生成本地投研结果；模型解释在确认任务中治理或安全降级" status={String(searchQuantProjectionReceipt.status ?? "local_receipt")}>
          <div className="actions">
            <input
              value={searchSymbol}
              onChange={(event) => {
                updateSearchSymbolInput(event.target.value);
                setQuantProjectionSubmitError("");
              }}
              placeholder="002008.SZ 或 002008"
              aria-label="search quant projection symbol"
              aria-describedby={quantProjectionFactorInputHelpId}
              title={quantProjectionInputBoundaryLabel}
            />
            <button
              disabled={quantProjectionSubmitDisabled}
              onClick={launchQuantProjection}
              title={quantProjectionSubmitButtonLabel}
              aria-label={quantProjectionSubmitAriaLabel}
              aria-describedby={quantProjectionFactorSubmitHelpId}
            >{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}</button>
            <a href="#factor" aria-label="open generated quant projection result">查看量化推演结果</a>
          </div>
          <p className="ordinary-status-note" aria-live="polite">{quantProjectionConnectionReadyLabel}</p>
          <div aria-label="quant projection ordinary one glance state">
            <h3>确认后一眼看懂</h3>
            <MetricGrid items={quantProjectionOrdinaryOneGlanceItems} />
          </div>
          {quantProjectionSubmitErrorLabel ? <p className="risk-note" aria-live="polite">{quantProjectionSubmitErrorLabel}</p> : null}
          {quantProjectionP0SubmitRecoveryRows.length ? (
            <div aria-label="quant projection p0 submit failure recovery">
              <h3>P0 恢复提示</h3>
            <p className="risk-note">确认按钮失败后先看本地联通恢复包：先做 check-only，再用一键启动恢复四段 ready；check-only 不启动服务，启动器只在用户运行时恢复 FastAPI/Vite；页面不会补调数据源或模型。</p>
              <DataLineageTable rows={quantProjectionP0SubmitRecoveryRows} />
            </div>
          ) : null}
          <StateClarityRail
            label="quant projection ordinary task status"
            state={quantProjectionOrdinaryTaskRailState}
            steps={quantProjectionOrdinaryTaskRailSteps}
          />
          <details className="developer-audit-details" aria-label="quant projection ordinary input and submit notes">
            <summary>输入与按钮状态</summary>
            <p id={quantProjectionFactorInputHelpId} className="risk-note" aria-live="polite">{quantProjectionInputSessionState}</p>
            <p id={quantProjectionFactorSubmitHelpId} className="risk-note" aria-live="polite">{quantProjectionDisabledReason}</p>
            <p className="risk-note" aria-live="polite">{quantProjectionSubmitHint}</p>
            <p className="risk-note" aria-live="polite">{quantProjectionTushareFirstState}</p>
            <p className="risk-note">普通确认状态：等待输入 / 任务接收 / 任务轮询 / cache 回放；这条状态轨只读本地 task receipt 和 cache，不补调 Tushare、DeepSeek 或 GitHub。</p>
          </details>
          <div aria-label="quant projection ordinary tushare data card">
            <h3>Tushare 数据卡</h3>
            <p className="ordinary-status-note" aria-label="quant projection ordinary tushare data card summary" aria-live="polite">{quantProjectionTushareDataCardSummary}</p>
            <MetricGrid items={quantProjectionTushareDataCardItems} />
            <details className="developer-audit-details" aria-label="quant projection ordinary tushare data card rows">
              <summary>查看接口回放</summary>
              <p className="risk-note">这张明细只读本地 Tushare light 接口回放；没有账本时显示等待或阻断，不从页面补调数据。</p>
              <DataLineageTable rows={quantProjectionTushareDataCardRows} />
            </details>
            <p className="risk-note">数据卡只整理确认后已有的本地 cache / call_ledger / packet；不会调用 Tushare、DeepSeek、GitHub，不交易、不改交易策略。</p>
          </div>
          <div aria-label="quant projection p1 visible progress summary">
            <h3>确认进度速读</h3>
            <p className="risk-note">点确认后先看这里：是否接收、最近确认、数据链和 P2 回放状态会直接出现在普通视图，不需要展开工程明细。</p>
            <MetricGrid items={quantProjectionP1ProgressItems} />
          </div>
          <details className="developer-audit-details" aria-label="quant projection ordinary p1 p2 immediate readback">
            <summary>P1/P2 即时回读表</summary>
            <h3>P1/P2 即时回读</h3>
            <p className="risk-note">普通主线先看上方一眼状态和确认进度速读；这两张 P1/P2 回放表默认收起，展开后只读 ordinary_confirm_outcome_rows 与 ordinary_writeback_surface_summary_rows，不创建第二个 task。</p>
            <DataLineageTable rows={quantProjectionOrdinaryConfirmOutcomeRows} />
            <DataLineageTable rows={quantProjectionWritebackSurfaceRows} />
          </details>
          <details className="developer-audit-details" aria-label="quant projection ordinary p1 p2 engineering details">
            <summary>查看任务与回放明细</summary>
            <p className="risk-note">普通主视图先保留状态轨、可读结论和回放入口；确认门控、task receipt、cache / ledger / packet 写入面默认收起，不影响确认按钮动作。</p>
          <div aria-label="quant projection ordinary confirm trigger boundary">
            <h3>P1 触发边界</h3>
            <p className="risk-note">优先读取服务端 ordinary_confirm_trigger_boundary_rows：输入只校验，确认按钮才创建 Tushare-first POST task，GET cache 和 React render 只回放本地结果。</p>
            <DataLineageTable rows={quantProjectionConfirmTriggerBoundaryRows} />
          </div>
          <div aria-label="quant projection p1 confirm gate checklist">
            <h3>P1 确认门控清单</h3>
            <p className="risk-note">优先读取服务端 ordinary_confirm_button_readiness_rows；先看代码是否通过本地校验，再点击一次确认按钮；提交后看 task id 和 TaskStatusPanel，失败先回 P0 联通恢复。这张表只读页面状态，不创建 task。</p>
            <DataLineageTable rows={quantProjectionP1ConfirmGateRows} />
          </div>
          <MetricGrid
            items={[
              { label: "确认状态", value: quantProjectionConfirmChainState, tone: taskReceipt?.ok || (quantProjectionCanLaunch && !quantProjectionSubmitError) ? "good" : "warn" },
              { label: "P1/P2 当前阶段", value: quantProjectionConfirmReplayStage, tone: quantProjectionSmallDataReady || taskReceipt?.ok || quantProjectionPersistedTaskId ? "good" : "warn" },
              { label: "Tushare-first", value: quantProjectionTushareFirstState, tone: quantProjectionProviderLedgerReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral" },
              { label: "小数据回放", value: quantProjectionSmallDataStageLabel, tone: quantProjectionSmallDataReady ? "good" : "warn" },
              { label: "可读结论", value: quantProjectionOrdinaryResultSummary, tone: quantProjectionInterpretationReady ? "good" : "warn" },
              { label: "下一步", value: quantProjectionOrdinaryResultNext },
              { label: "安全边界", value: "不交易、不改 strategy action；DeepSeek 只读解释可安全降级；不交易、不改交易策略", tone: "good" }
            ]}
          />
          <div aria-label="quant projection ordinary end to end path">
            <h3>四步端到端路径</h3>
            <p className="risk-note">先确认本地连接，再输入代码、点击确认、回放结果；只有点击确认会创建后台任务。</p>
            <DataLineageTable rows={quantProjectionOrdinaryEndToEndRows} />
          </div>
          <div aria-label="quant projection ordinary confirmation handoff">
            <p className="risk-note">确认后链路回放：优先读取服务端 ordinary_tushare_first_chain_rows；输入只校验，点击确认才创建 Tushare-first 后台任务，结果只从本地 cache / ledger / packet 回放。</p>
            <DataLineageTable rows={quantProjectionConfirmHandoffRows} />
          </div>
          <div aria-label="quant projection confirmed task receipt readback">
            <h3>确认任务接收回执</h3>
            <p className="risk-note">点击确认后先看这张回执：它只回放本地 POST task 是否接收、Tushare-first / DeepSeek 只读解释参数和安全步骤；回放本身不补调数据源或模型。</p>
            <DataLineageTable rows={quantProjectionConfirmedTaskReceiptRows} />
          </div>
          <div aria-label="quant projection persisted task resume">
            <h3>刷新后继续任务</h3>
            <p className="risk-note">页面刷新后优先用 quantProjectionPersistedTaskId 恢复最近确认任务；TaskStatusPanel 只轮询本地 FastAPI，不创建新 task、不补调 Tushare/DeepSeek。</p>
            <DataLineageTable rows={quantProjectionResumeTaskRows.length ? quantProjectionResumeTaskRows : quantProjectionTaskCacheReadbackRows} />
          </div>
          <div aria-label="quant projection post confirm user actions">
            <h3>确认后看什么</h3>
            <p className="risk-note">点击确认后先看任务编号和 TaskStatusPanel，再刷新本地 cache，最后回放量化推演和次日图谱；这些行动不会创建第二个外部补证任务。</p>
            <DataLineageTable rows={quantProjectionPostConfirmActionRows} />
          </div>
          <div aria-label="quant projection ordinary small data writeback targets">
            <h3>小数据写入位置</h3>
            <p className="risk-note">{quantProjectionSmallDataWritebackStatus}</p>
            <div aria-label="quant projection ordinary p2 writeback integrity">
              <h3>P2 三面完整性检查</h3>
              <p className="risk-note">优先读取服务端 ordinary_writeback_integrity_rows：普通用户只看 cache、call_ledger、packet 三面是否齐备；这张表只读回放，不创建 task。</p>
              <DataLineageTable rows={quantProjectionWritebackIntegrityRows} />
            </div>
            <div aria-label="quant projection ordinary writeback surface summary">
              <h3>P2 写入面速读</h3>
              <p className="risk-note">优先读取服务端 ordinary_writeback_surface_summary_rows：普通入口只看 cache、call_ledger、packet 三个写入面是否可回放；GET cache 不创建 task。</p>
              <DataLineageTable rows={quantProjectionWritebackSurfaceRows} />
            </div>
            {quantProjectionSmallDataActionRows.length ? (
              <div aria-label="quant projection ordinary small data writeback actions">
                <h3>小数据行动清单</h3>
                <p className="risk-note">优先读取服务端 ordinary_writeback_action_rows：看任务、看 ledger、刷新 cache、回放结果；不会从回放行创建 task。</p>
                <DataLineageTable rows={quantProjectionSmallDataActionRows} />
              </div>
            ) : null}
            <DataLineageTable rows={quantProjectionSmallDataWritebackRows} />
          </div>
          </details>
          <div id="next" aria-label="quant projection ordinary explainable result readback">
            <h3>解释结果清单</h3>
            <p className="risk-note">普通入口只回放数据来源、量化推演、次日图谱和安全边界；原始 receipt、prompt 或审计字段仍下沉在详情中。</p>
            <details className="developer-audit-details" aria-label="quant projection ordinary readback index">
              <summary>P2/P3 回放索引</summary>
              <p className="risk-note">读取本地 packet 回放索引：确认回执、任务回放、数据接口和 P3 结果速读都只做本地回放，不创建 task。</p>
              <DataLineageTable rows={quantProjectionReadbackIndexRows} />
            </details>
            <div aria-label="quant projection ordinary explainable result quick read">
              <h3>P3 结果速读</h3>
              <p className="ordinary-status-note" aria-label="quant projection ordinary p3 readable sentence">{quantProjectionP3OrdinaryReadableSentence}</p>
              <div aria-label="quant projection ordinary p3 result summary strip">
                <MetricGrid items={quantProjectionP3ResultSummaryItems} />
              </div>
              <p className="risk-note">优先读取服务端 ordinary_result_quick_read_rows：先看可读结论、来源组成、回放来源和待补证据；不会从结果速读创建 task 或调用模型。</p>
              <div aria-label="quant projection ordinary result checkpoint">
                <h3>P3 结果检查点</h3>
                <p className="risk-note">优先读取服务端 ordinary_result_checkpoint_rows：确认可读结论、来源、缺口和安全字段；这张检查点表只读本地 cache，不创建 task、不调用模型。</p>
                <DataLineageTable rows={quantProjectionOrdinaryResultCheckpointRows} />
              </div>
              {quantProjectionOrdinaryResultHandoffRows.length ? (
                <div aria-label="quant projection ordinary result handoff index">
                  <h3>P3 结果入口索引</h3>
                  <p className="risk-note">优先读取服务端 ordinary_result_handoff_rows：把可读结论、量化推演、次日图谱和候选池绑定到同一个本地来源任务；链接只切换入口，不创建 task。</p>
                  <DataLineageTable rows={quantProjectionOrdinaryResultHandoffRows} />
                </div>
              ) : null}
              <DataLineageTable rows={quantProjectionOrdinaryResultQuickRows} />
            </div>
            <details className="developer-audit-details" aria-label="quant projection ordinary deepseek governance status">
              <summary>高级：DeepSeek 解释治理</summary>
              <p className="risk-note">这里优先读取 ordinary_model_governance_rows，说明按钮门控模型解释何时可回放或安全降级；不作为数据源，不阻塞 P1/P2/P3 本地回放，不会从治理状态创建 task 或调用模型。</p>
              {quantProjectionDeepSeekContractRows.length ? (
                <div aria-label="quant projection ordinary deepseek governed executor contract">
                  <h3>DeepSeek 解释治理合同</h3>
                  <p className="risk-note">优先读取服务端 ordinary_deepseek_governed_executor_contract_rows：确认按钮后的解释必须有 model_ledger、sanitizer、output acceptance、安全字段和不阻塞 P1/P2/P3；这张表只读回放，不创建 task、不调用模型。</p>
                  <DataLineageTable rows={quantProjectionDeepSeekContractRows} />
                </div>
              ) : null}
              {quantProjectionDeepSeekReadinessRows.length ? (
                <div aria-label="quant projection ordinary deepseek governed executor readiness">
                  <h3>P5 governed executor readiness</h3>
                  <p className="risk-note">优先读取服务端 ordinary_deepseek_governed_executor_readiness_rows：说明何时允许 DeepSeek 解释、当前是否安全降级、以及只能写安全摘要；这张表只读回放，不创建 task、不调用模型。</p>
                  <DataLineageTable rows={quantProjectionDeepSeekReadinessRows} />
                </div>
              ) : null}
              <DataLineageTable rows={quantProjectionDeepSeekGovernanceRows} />
              {quantProjectionDeepSeekChecklistRows.length ? (
                <div aria-label="quant projection ordinary deepseek governed executor checklist">
                  <h3>P5 governed executor 补证清单</h3>
                  <p className="risk-note">优先读取服务端 ordinary_deepseek_governed_executor_checklist_rows：model_ledger、sanitizer/redaction、output acceptance、安全回退和不覆盖 action 都必须先满足；这张清单不创建 task、不调用模型。</p>
                  <DataLineageTable rows={quantProjectionDeepSeekChecklistRows} />
                </div>
              ) : null}
            </details>
            <DataLineageTable rows={quantProjectionOrdinaryResultRows} />
          </div>
          <div aria-label="quant projection ordinary explainable result actions">
            <h3>可解释结果行动</h3>
            <p className="risk-note">优先读取服务端 ordinary_result_action_rows：读可读结论、回放量化推演、打开次日图谱，并保持仅供研究边界。</p>
            <DataLineageTable rows={quantProjectionOrdinaryResultActionRows} />
          </div>
          <div className="actions" aria-label="quant projection replay destinations">
            <a href="#factor" title="切换到股票量化推演模块；只读 cache / ledger / packet，不创建 task" aria-label="replay generated stock quant projection">回放股票量化推演</a>
            <a href="#next" title="切换到次日图谱模块；只读本地 next-session cache，不创建 task" aria-label="replay generated next session map">回放次日图谱</a>
            <a href="#candidate-pool" title="跳回本页候选池锚点；不重新扫描、不创建 task" aria-label="return to candidate pool after quant projection">回到候选池</a>
          </div>
          <div aria-label="quant projection replay destination readiness">
            <p className="risk-note">{quantProjectionReplayDestinationState}</p>
            <DataLineageTable rows={quantProjectionReplayDestinationRows} />
          </div>
          <details className="developer-audit-details" aria-label="quant projection task cache packet readback">
            <summary>任务 / cache packet 回放详情</summary>
            <h3>任务回放清单</h3>
            <p className="risk-note">普通入口只保留任务状态轨和结果速读；task id、safe current_step、cache packet 明细默认收起。</p>
            <p className="risk-note">任务编号和安全步骤优先从本地 cache / packet 回放；TaskStatusPanel 只轮询本地 FastAPI 任务状态。</p>
            <p className="risk-note">{quantProjectionSmallDataProvenance}</p>
            <DataLineageTable rows={quantProjectionTaskCacheReadbackRows} />
          </details>
          <details className="developer-audit-details" aria-label="quant projection advanced status readback">
            <summary>高级状态回放</summary>
            <MetricGrid
              items={[
                { label: "下一步", value: quantProjectionNextClick },
                { label: "输入标的", value: quantProjectionDisplaySymbol || "等待输入" },
                { label: "确认代码", value: quantProjectionConfirmedSymbol },
                { label: "确认链路", value: quantProjectionConfirmChainState, tone: taskReceipt?.ok || (quantProjectionCanSubmit && !quantProjectionSubmitError) ? "good" : "warn" },
                { label: "输入校验", value: quantProjectionInputValidation, tone: quantProjectionInputValidation.includes("阻断") ? "warn" : "good" },
                { label: "Tushare-first", value: quantProjectionTushareFirstState, tone: quantProjectionProviderLedgerReady ? "good" : taskReceipt?.ok || quantProjectionPersistedTaskId ? "warn" : "neutral" },
                { label: "Tushare ledger", value: quantProjectionProviderModelReplayState, tone: quantProjectionProviderLedgerReady ? "good" : "warn" },
                { label: "cache / ledger / packet", value: quantProjectionSmallDataReplayState, tone: quantProjectionSmallDataReady ? "good" : "warn" },
                { label: "小数据下一步", value: quantProjectionSmallDataNextStep, tone: quantProjectionSmallDataReady ? "good" : "warn" },
                { label: "小数据写入", value: quantProjectionSmallDataWritebackSurfaces, tone: quantProjectionSmallDataReady ? "good" : "warn" },
                { label: "provider 来源", value: quantProjectionProviderCallSource, tone: quantProjectionProviderLedgerReady ? "good" : "warn" },
                { label: "回放合同", value: quantProjectionSmallDataReadbackContract, tone: "good" },
                { label: "投研图谱联动", value: quantProjectionResearchMapState, tone: quantProjectionFactorNextReady ? "good" : "warn" },
                { label: "结论下一步", value: quantProjectionOrdinaryResultNext },
                { label: "结论证据", value: quantProjectionOrdinaryResultEvidence },
                { label: "结论边界", value: quantProjectionOrdinaryResultBoundary, tone: "good" },
                { label: "解释结果", value: quantProjectionInterpretationState, tone: quantProjectionInterpretationReady ? "good" : "warn" },
                { label: "解释下一步", value: quantProjectionInterpretationNext },
                { label: "图谱下一步", value: quantProjectionMapNextStep },
                { label: "数据来源状态", value: quantProjectionSourceState },
                { label: "任务边界", value: quantProjectionTaskBoundary },
                { label: "任务回放", value: quantProjectionTaskReadbackState, tone: quantProjectionPersistedTaskId ? "good" : "warn" },
                { label: "缺少证据", value: quantProjectionMissingEvidence, tone: quantProjectionMissingEvidence.includes("证据") || quantProjectionMissingEvidence.includes("验收") || quantProjectionMissingEvidence.includes("申请") ? "warn" : "good" },
                { label: "阻断/降级", value: quantProjectionBlockedState, tone: quantProjectionBlockedState.includes("阻断") || quantProjectionBlockedState.includes("未通过") ? "warn" : "good" },
                { label: "最近可用结果", value: quantProjectionLastResult },
                { label: "最近任务", value: quantProjectionLatestTaskState, tone: taskReceipt?.ok === false ? "warn" : "good" },
                { label: "结果位置", value: quantProjectionResultLocation, tone: "good" },
                { label: "结果回放", value: quantProjectionInterpretationReplay || quantProjectionResultReplayState, tone: "good" },
                { label: "回放顺序", value: quantProjectionReplayOrder, tone: taskReceipt?.ok || quantProjectionProviderLedgerReady ? "good" : "warn" },
                { label: "回放边界", value: quantProjectionReplayBoundary, tone: "good" },
                { label: "仅供研究", value: "推演解释只整理已有证据；不覆盖价格、持仓、因子、操作区或交易策略", tone: "good" }
              ]}
            />
            {quantProjectionSmallDataRows.length ? (
              <DataLineageTable rows={quantProjectionSmallDataRows} />
            ) : null}
            {quantProjectionProviderApiRows.length ? (
              <div aria-label="quant projection tushare light api replay">
                <h3>Tushare light 接口回放</h3>
                <p className="risk-note">这里逐项回放 trade_cal / daily / daily_basic / moneyflow 的本地 ledger 状态；表格只读，不补调数据源或模型。</p>
                <DataLineageTable rows={quantProjectionProviderApiRows} />
              </div>
            ) : null}
          </details>
          {quantProjectionTaskPanelVisible ? (
            <div aria-label="quant projection tushare-first task status handoff">
              <p className="ordinary-status-note">任务状态面板已固定在确认后一屏结果；这里保留回放提示，避免同一任务在普通入口重复轮询。</p>
            </div>
          ) : null}
          {quantProjectionTaskPanelStaleNotice ? (
            <p className="ordinary-status-note" aria-live="polite">{quantProjectionTaskPanelStaleNotice}</p>
          ) : null}
          <p className="risk-note">普通入口只保留确认按钮、任务状态和结果回放；确认链路、cache packet、provider ledger 等工程说明默认收起。</p>
          <details className="developer-audit-details" aria-label="quant projection confirm chain explanation details">
            <summary>确认链路细节</summary>
            <p className="risk-note">任务接收后立即回读本地 cache receipt，再看最近任务编号和 TaskStatusPanel；成功后刷新本地缓存，再打开股票量化推演和次日图谱回放入口。</p>
            <p className="risk-note">最近任务优先显示本次确认返回的 task id；页面刷新后再从本地 cache / packet 回放 task id 和安全 current_step；GET cache 不会因此补调 provider。</p>
            <p className="risk-note">确认按钮只提交后台链路；服务端凭据可用才写入 Tushare call_ledger / cache / packet，凭据缺失只写本地阻断，GET cache 和 React render 不补调 provider。</p>
            <p>普通入口保留“确认并生成”作为 P1 主按钮；点击后在本卡显示任务接收和状态，DeepSeek 只读解释可安全降级，不交易、不改交易策略；审计原文：不交易、不改 strategy action。</p>
            <p>最近任务只显示本地 FastAPI 返回的 task id 和安全步骤；结果成功后通过 GET cache 回放 packet / ledger，不在普通页面展开审计表。</p>
            <p className="risk-note">Tushare ledger 来自 cache / call_ledger 回放；DeepSeek 只展示 sanitized explanation / model_ledger，普通页不展示 prompt/output。</p>
            <p>确认后创建 Tushare-first 按钮门控 POST task / worker；Tushare 小全量数据写入 call_ledger；DeepSeek 只读解释可成功或安全降级，React render 不直接外联。</p>
          </details>
          <details className="developer-audit-details">
            <summary>搜票推演记录详情</summary>
            <p>标的: {String(searchQuantProjectionReceipt.symbol ?? "--")}；代码有效: {String(searchQuantProjectionReceipt.symbol_valid === true)}；可进入真实数据源/模型推演: {String(searchQuantProjectionReceipt.ready_for_real_provider_model_projection === true)}</p>
            <p>Tushare 记录可见: {String(searchQuantProjectionReceipt.provider_execution_implemented === true)}；DeepSeek 记录可见: {String(searchQuantProjectionReceipt.model_execution_implemented === true)}；生产级推演完成: {String(searchQuantProjectionReceipt.production_quant_projection_complete === true)}</p>
            <p>Tushare 已调用: {String(searchQuantProjectionReceipt.tushare_called === true)}；DeepSeek 已调用: {String(searchQuantProjectionReceipt.deepseek_called === true)}；候选不是买入指令: {String(searchQuantProjectionReceipt.candidate_is_not_buy_instruction !== false)}</p>
            <DataLineageTable rows={objectRow(searchQuantProjectionReceipt)} />
            <DataLineageTable rows={searchQuantProjectionRows} />
          </details>
        </PacketCard>
        </div>

        <details className="developer-audit-details" aria-label="candidate radar optional scan tools details">
          <summary>可选扫描 / 高级补证入口</summary>
          <p className="risk-note">P1 主路径保留在上方搜票量化推演；本地快扫、自选池、full-pool/deep-scan 只作可选补证，默认收起，不从页面打开或输入触发 provider/model。</p>
          <PacketCard title="快速雷达扫描" subtitle="手动刷新本地快扫、自选池或输入股票池；不自动外联" status={String(scanCoverage.coverage_status ?? "cache")}>
            <div className="actions">
              <button onClick={refreshCache}>查看本地缓存</button>
              <button onClick={launchQuickScan}>运行本地快扫</button>
              <button onClick={launchWatchlistScan}>扫描本地自选</button>
            </div>
            <textarea
              value={customPoolText}
              onChange={(event) => setCustomPoolText(event.target.value)}
              placeholder="002008.SZ, 002837.SZ"
              rows={3}
            />
            <div className="actions">
              <button onClick={launchCustomScan}>扫描输入股票池</button>
            </div>
            <details className="developer-audit-details">
              <summary>高级扫描 / 全池深研</summary>
              <p>全池/深研按钮默认收起；普通用户先运行本地快扫或扫描自选/输入池，生产替代补证再进入这里。</p>
              <div className="actions">
                <button onClick={launchFullPoolPlan}>规划全池扫描</button>
                <button onClick={launchFullPoolLocalScan}>保存本地全池记录</button>
                <button onClick={launchDeepScanPlan}>整理深研清单</button>
                <button onClick={launchDeepScanLocalReview}>检查本地深研证据</button>
              </div>
            </details>
            <p>本地快扫只重建缓存和标记覆盖缺口，不调用 Tushare、DeepSeek 或 GitHub。</p>
            <p>信号覆盖、旧雷达能力映射和跳过原因会保留在详情里，避免静默丢失能力。</p>
            <p>缺失、跳过、陈旧或未知输入会作为仅供研究的缺口展示。</p>
            <details className="developer-audit-details">
              <summary>最近操作记录</summary>
              <TaskLaunchReceipt receipt={taskReceipt} />
              {manualTaskPanelVisible ? (
                <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
              ) : (
                <p className="ordinary-status-note" aria-live="polite">{manualTaskPanelEmptyNotice}</p>
              )}
            </details>
            <details className="developer-audit-details">
              <summary>快速扫描覆盖详情</summary>
              <p>任务血缘写入 local_candidate_radar_[scan_mode]，GET cache 仍然只读。</p>
              <p>quick_scan_reads_cache_only: {String(policy.quick_scan_reads_cache_only === true)}</p>
              <DataLineageTable rows={objectRow(scanCoverage)} />
            </details>
          </PacketCard>
        </details>

        <details id="settings" className="developer-audit-details" aria-label="candidate radar settings audit details">
          <summary>运行模式 / provider-model 审计</summary>
          <PacketCard title="雷达运行模式分层" subtitle="GET /api/bootstrap/status；雷达页只读展示 cache_only / manual / live_light 边界" status={String(bootstrapStatus.status ?? "cache_only")}>
            <p>runtime mode: {String(bootstrapStatus.mode ?? "cache_only")}；live_light enabled: {String(bootstrapLiveLight.enabled === true)}</p>
            <p>Tushare 自动刷新 / DeepSeek pro 自动解释: {String(bootstrapLiveLight.tushare_on_open === true)} / {String(bootstrapLiveLight.deepseek_on_open === true)}</p>
            <p>symbol_limit / rate_limit_seconds: {String(bootstrapLiveLight.symbol_limit ?? "--")} / {String(bootstrapLiveLight.rate_limit_seconds ?? "--")}</p>
            <p>bootstrap_task_implemented: {String(bootstrapLiveLight.bootstrap_task_implemented === true)}；provider_execution_implemented / model_execution_implemented: {String(bootstrapLiveLight.provider_execution_implemented === true)} / {String(bootstrapLiveLight.model_execution_implemented === true)}</p>
            <p>provider/model release switch configured / effective: {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_configured ?? false)} / {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_effective ?? false)}</p>
            <p>provider/model requires live_light / execution request / promotion: {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_live_light ?? false)} / {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_execution_request ?? false)} / {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_requires_promotion ?? false)}</p>
            <p>provider/model creates task / calls now: {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_creates_provider_model_task ?? false)} / {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_calls_provider_model_now ?? false)}</p>
            <p>provider/model release switch production evidence: {String(bootstrapRuntimeOperatorSummary.provider_model_enablement_summary_is_production_evidence ?? false)}</p>
            <p>activation receipt: {String(bootstrapActivationReceipt.status ?? "--")}；雷达页不会直接调用 Tushare、DeepSeek、GitHub，也不会从 render 启动 full-pool 或 deep-scan。</p>
            <p>live_light 后台审计：轻量实时后台任务只允许确认按钮创建 POST task；普通摘要不展示工程任务噪音。</p>
            <DataLineageTable rows={bootstrapProviderModelEnablementRows} />
            <DataLineageTable rows={bootstrapModeRows} />
            <DataLineageTable rows={bootstrapConfigRows} />
            <DataLineageTable rows={bootstrapProviderLinkageRows} />
            <DataLineageTable rows={bootstrapEnvelopeLedger} />
            {bootstrapWarningRows.length ? <DataLineageTable rows={bootstrapWarningRows} /> : null}
          </PacketCard>
        </details>

        <details id="candidate-radar-ltg13-data-ledger-audit" className="developer-audit-details">
          <summary>Tushare/DeepSeek 联动验收</summary>
          <PacketCard title="Tushare/DeepSeek 联动审查" subtitle="search_quant_projection_activation_receipt / rows；只组织下一步验收，不代表真实外联完成" status={String(searchQuantProjectionActivation.status ?? "missing")}>
            <div className="actions">
              <button onClick={launchQuantProjectionAcceptanceDryRun}>运行联动 dry-run</button>
            </div>
            <p>local_activation_receipt_ready: {String(searchQuantProjectionActivation.local_activation_receipt_ready === true)}</p>
            <p>allowed_next_step: {String(searchQuantProjectionActivation.allowed_next_step ?? "--")}</p>
            <p>ready_for_real_provider_model_projection: {String(searchQuantProjectionActivation.ready_for_real_provider_model_projection === true)}；production_quant_projection_complete: {String(searchQuantProjectionActivation.production_quant_projection_complete === true)}</p>
            <p>provider_execution_implemented: {String(searchQuantProjectionActivation.provider_execution_implemented === true)}；model_execution_implemented: {String(searchQuantProjectionActivation.model_execution_implemented === true)}</p>
            <p>factor_refresh_executed: {String(searchQuantProjectionActivation.factor_refresh_executed === true)}；next_session_refresh_executed: {String(searchQuantProjectionActivation.next_session_refresh_executed === true)}；echarts_payload_refreshed: {String(searchQuantProjectionActivation.echarts_payload_refreshed === true)}</p>
            <p>tushare_called: {String(searchQuantProjectionActivation.tushare_called === true)}；deepseek_called: {String(searchQuantProjectionActivation.deepseek_called === true)}；github_called: {String(searchQuantProjectionActivation.github_called === true)}</p>
            <p>这个收据把真实 Tushare light call_ledger、可选 DeepSeek pro model_ledger、Factor/Next/ECharts 刷新、浏览器非阻塞证据和 promotion review 分层列出；它不会从 render 调 provider，也不会生成交易指令。</p>
            <DataLineageTable rows={objectRow(searchQuantProjectionActivation)} />
            <DataLineageTable rows={searchQuantProjectionActivationRows} />
            <p>search_quant_projection_acceptance_dry_run_receipt: {String(searchQuantProjectionAcceptanceDryRun.status ?? "missing")}；ready_for_user_approved_real_acceptance: {String(searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true)}</p>
            <p>acceptance_scope_hash_short: {String(searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash_short ?? "--")}；credential_missing_provider_count: {String(searchQuantProjectionAcceptanceDryRun.credential_missing_provider_count ?? "--")}</p>
            <p>credential_values_read: {String(searchQuantProjectionAcceptanceDryRun.credential_values_read === true)}；credential_values_exposed: {String(searchQuantProjectionAcceptanceDryRun.credential_values_exposed === true)}；env_key_names_included: {String(searchQuantProjectionAcceptanceDryRun.env_key_names_included === true)}</p>
            <DataLineageTable rows={objectRow(searchQuantProjectionAcceptanceDryRun)} />
            <DataLineageTable rows={searchQuantProjectionAcceptanceDryRunRows} />
            <DataLineageTable rows={searchQuantProjectionCredentialRows} />
            <div className="actions">
              <button
                onClick={launchQuantProjectionExecutionRequest}
                disabled={!searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash}
                title={searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash ? "绑定 dry-run scope hash；不创建 provider/model task" : "先运行联动 dry-run 生成 acceptance scope hash"}
                aria-label="create provider model execution request after dry run scope hash"
              >
                生成 provider/model execution request
              </button>
            </div>
            <p>search_quant_projection_execution_request_receipt: {String(searchQuantProjectionExecutionRequest.status ?? "missing")}；local_execution_request_ready: {String(searchQuantProjectionExecutionRequest.local_execution_request_ready === true)}</p>
            <p>requested scope matches latest: {String(searchQuantProjectionExecutionRequest.requested_acceptance_scope_hash_matches_latest === true)}；scope: {String(searchQuantProjectionExecutionRequest.acceptance_scope_hash_short ?? "--")}</p>
            <p>target: {String(searchQuantProjectionExecutionRequest.target_provider_model_route ?? "future POST /api/candidate-radar/quant-projection-provider-model-acceptance")}</p>
            <p>provider_model_task_created / dispatched: {String(searchQuantProjectionExecutionRequest.provider_model_task_created === true)} / {String(searchQuantProjectionExecutionRequest.provider_model_task_dispatched === true)}</p>
            <p>provider_execution_implemented / model_execution_implemented: {String(searchQuantProjectionExecutionRequest.provider_execution_implemented === true)} / {String(searchQuantProjectionExecutionRequest.model_execution_implemented === true)}</p>
            <p>factor / next / echarts refreshed: {String(searchQuantProjectionExecutionRequest.factor_refresh_executed === true)} / {String(searchQuantProjectionExecutionRequest.next_session_refresh_executed === true)} / {String(searchQuantProjectionExecutionRequest.echarts_payload_refreshed === true)}</p>
            <p>tushare_called / deepseek_called / github_called: {String(searchQuantProjectionExecutionRequest.tushare_called === true)} / {String(searchQuantProjectionExecutionRequest.deepseek_called === true)} / {String(searchQuantProjectionExecutionRequest.github_called === true)}</p>
            <p>这个 execution request 只绑定 dry-run scope hash 和用户确认；它不创建真实 provider/model task，不调用 Tushare/DeepSeek，不刷新图谱，不生成交易指令。</p>
            <div className="actions">
              <button
                onClick={launchQuantProjectionProviderModelAcceptance}
                disabled={!searchQuantProjectionExecutionRequest.acceptance_scope_hash}
                title={searchQuantProjectionExecutionRequest.acceptance_scope_hash ? "按钮门控 Tushare-first 补证；仍不交易、不改 strategy action" : "先生成 provider/model execution request scope hash"}
                aria-label="confirm Tushare first evidence after execution request scope hash"
              >
                确认 Tushare-first 补证
              </button>
              <button
                onClick={launchQuantProjectionDeepSeekFailureAcceptance}
                disabled={!searchQuantProjectionExecutionRequest.acceptance_scope_hash}
                title={searchQuantProjectionExecutionRequest.acceptance_scope_hash ? "按钮门控 DeepSeek 安全降级验收；保留 Tushare/Factor/Next 结果" : "先生成 provider/model execution request scope hash"}
                aria-label="verify DeepSeek safe degraded after execution request scope hash"
              >
                验证 DeepSeek 安全降级
              </button>
            </div>
            <p>该按钮只在 execution request 有 scope hash 后可点；它通过 POST task 触发 Tushare light provider ledger，DeepSeek 只读解释可安全降级，仍不交易、不改交易策略；审计原文：不交易、不改 strategy action。</p>
            <p>DeepSeek 安全降级按钮只用于验收模型不可用分支：同一个 scope hash 下先保留 Tushare / Factor / Next 事实结果，再记录 missing_server_key 降级账本；它不把模型当数据源，也不提升为 production complete。</p>
            <p>点击后本区域会显示任务创建记录和状态；成功后自动刷新本地 cache，下一轮 GET 只回放 search_quant_provider_model_acceptance_receipt / call_ledger / packet，不在 React render 里补调 provider。</p>
            <TaskLaunchReceipt receipt={taskReceipt} />
            {manualTaskPanelVisible ? (
              <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
            ) : (
              <p className="ordinary-status-note" aria-live="polite">{manualTaskPanelEmptyNotice}</p>
            )}
            <DataLineageTable rows={objectRow(searchQuantProjectionExecutionRequest)} />
            <DataLineageTable rows={searchQuantProjectionExecutionRequestRows} />
          </PacketCard>
        </details>

        <details className="developer-audit-details">
          <summary>Provider coverage 验收</summary>
          <PacketCard title="雷达 provider coverage dry-run" subtitle="POST /api/candidate-radar/provider-parity-dry-run；本地预检，不调用 Tushare/DeepSeek" status={String(providerParityDryRun.status ?? "missing")}>
            <div className="actions">
              <button onClick={launchProviderParityDryRun}>运行雷达 provider coverage dry-run</button>
            </div>
            <p>ready_for_user_approved_provider_parity: {String(providerParityDryRun.ready_for_user_approved_provider_parity === true)}；ready_to_execute_real_provider_parity_task: {String(providerParityDryRun.ready_to_execute_real_provider_parity_task === true)}</p>
            <p>candidate_symbol_count: {String(providerParityDryRun.candidate_symbol_count ?? 0)}；provider_coverage_gap_count: {String(providerParityDryRun.provider_coverage_gap_count ?? 0)}；acceptance_scope_hash_short: {String(providerParityDryRun.acceptance_scope_hash_short ?? "--")}</p>
            <p>provider_execution_implemented: {String(providerParityDryRun.provider_execution_implemented === true)}；model_execution_implemented: {String(providerParityDryRun.model_execution_implemented === true)}；production_radar_replacement_complete: {String(providerParityDryRun.production_radar_replacement_complete === true)}</p>
            <p>credential_values_read: {String(providerParityDryRun.credential_values_read === true)}；credential_values_exposed: {String(providerParityDryRun.credential_values_exposed === true)}；env_key_names_included: {String(providerParityDryRun.env_key_names_included === true)}</p>
            <p>这个 dry-run 只把下一票雷达的 provider-backed coverage、full-pool worker、deep-scan worker、浏览器性能和 DeepSeek model ledger 验收范围固定住；它不会从 render 调 provider，也不会退掉 legacy fallback。</p>
            <DataLineageTable rows={objectRow(providerParityDryRun)} />
            <DataLineageTable rows={providerParityDryRunRows} />
            <DataLineageTable rows={providerParityCredentialRows} />
          </PacketCard>
        </details>

      </div>

      <details id="audit" className="developer-audit-details" aria-label="candidate radar developer audit details">
        <summary>开发 / 审计指标</summary>
        <p>Provider、worker、receipt、browser QA、retained coverage 和 production blocker 明细默认收起；普通用户先看上方雷达摘要、候选池和搜票量化推演；也就是先查看本地候选摘要，再继续搜票量化推演。</p>
        <details className="developer-audit-details" aria-label="candidate radar audit evidence route details">
          <summary>补证路线 / 缺口审计</summary>
          <p className="risk-note">P4 将补证路线从普通主卡下沉到开发审计区；普通用户先看 P1 确认、P2 三面和 P3 结果证据，补证路线只作为后续人工排查参考。</p>
          <PacketCard title="补证路线概览" subtitle="只整理候选证据和待补路线，不生成交易动作" status={String(overview.tone ?? overview.status ?? "cache")}>
            <MetricGrid
              items={[
                { label: "证据摘要", value: String(overview.headline ?? "--") },
                { label: "当前阶段", value: String(overview.stage_text ?? "--") },
                { label: "研究边界", value: String(overview.decision_guardrail ?? "--"), tone: "good" }
              ]}
            />
          </PacketCard>
        </details>
        <details className="developer-audit-details" aria-label="candidate radar audit p5 governance details">
          <summary>DeepSeek 解释治理状态</summary>
          <p className="risk-note">P4 将模型治理状态下沉到开发审计区；普通主线先看 P1 确认、P2 三面回放和 P3 结果速读，DeepSeek 只作为解释层回放或安全降级。</p>
          <div aria-label="candidate radar audit p5 deepseek standalone governance">
            <h3>DeepSeek 解释治理速读</h3>
            <p className="risk-note">DeepSeek 只作为 governed explanation；P1 Tushare-first、P2 小数据写入和 P3 基础图谱继续先走本地回放，不等待模型。</p>
            <DataLineageTable rows={quantProjectionDeepSeekGovernanceRows} />
          </div>
          <div aria-label="candidate radar audit p5 governed executor contract">
            <h3>DeepSeek 解释治理合同</h3>
            <p className="risk-note">优先读取服务端 ordinary_deepseek_governed_executor_contract_rows：DeepSeek 解释必须有 model_ledger、sanitizer、output acceptance 和安全摘要字段；本表只读回放，不创建 task、不调用模型。</p>
            <DataLineageTable rows={quantProjectionDeepSeekContractRows} />
          </div>
          <div aria-label="candidate radar audit p5 governed executor readiness">
            <h3>P5 governed executor readiness</h3>
            <p className="risk-note">高级审计只看 P5 是否具备单独补证条件：model_ledger、sanitizer、output acceptance、fallback 和 promotion 边界；这张表只读回放，不创建 task、不调用模型。</p>
            <DataLineageTable rows={quantProjectionDeepSeekReadinessRows} />
          </div>
        </details>
        <details className="developer-audit-details" aria-label="candidate radar audit p6 strict closeout handoff">
          <summary>P6 14 LTG strict closeout 交接</summary>
          <p className="risk-note">P4 将 14 LTG strict closeout 交接下沉到开发审计区；当前只是使用者可用化 checkpoint，不是 14 LTG 全部完成，后续必须回到 direct evidence、CI、browser/provider/worker/storage/package 等逐项严格验收。</p>
        </details>
        <MetricGrid
          items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "runtime mode", value: String(bootstrapStatus.mode ?? "cache_only"), tone: bootstrapStatus.mode === "live_light" ? "warn" : "good" },
          { label: "live_light", value: bootstrapLiveLight.enabled === true ? "enabled" : "off", tone: bootstrapLiveLight.enabled === true ? "warn" : "good" },
          { label: "auto Tushare", value: bootstrapLiveLight.tushare_on_open === true ? "on" : "off", tone: bootstrapLiveLight.tushare_on_open === true ? "warn" : "good" },
          { label: "auto DeepSeek", value: bootstrapLiveLight.deepseek_on_open === true ? "on" : "off", tone: bootstrapLiveLight.deepseek_on_open === true ? "warn" : "good" },
          { label: "bootstrap task", value: bootstrapLiveLight.bootstrap_task_implemented === true ? "ready" : "pending", tone: bootstrapLiveLight.bootstrap_task_implemented === true ? "good" : "warn" },
          { label: "候选数", value: counts.candidate_count as number | undefined },
          { label: "可准备", value: counts.ready_count as number | undefined },
          { label: "只观察", value: counts.observe_count as number | undefined },
          { label: "待验证", value: counts.verify_count as number | undefined },
          { label: "scan mode", value: String(cache.scan_mode ?? "--") },
          { label: "scan family", value: String(scanExecutionSummary.scan_family ?? "--") },
          { label: "quick receipt", value: String(quickScanReceipt.status ?? "missing"), tone: quickScanReceipt.local_quick_scan_receipt_ready === true ? "good" : "warn" },
          { label: "task pipeline", value: String(fastScanTaskPipeline.status ?? "missing"), tone: fastScanTaskPipeline.local_task_pipeline_ready === true ? "good" : "warn" },
          { label: "pipeline blockers", value: counts.fast_scan_task_pipeline_production_blocker_count as number | undefined, tone: Number(counts.fast_scan_task_pipeline_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "receipt blockers", value: counts.quick_scan_receipt_production_blocker_count as number | undefined, tone: Number(counts.quick_scan_receipt_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "receipt provider", value: counts.quick_scan_receipt_provider_gap_count as number | undefined, tone: Number(counts.quick_scan_receipt_provider_gap_count ?? 0) ? "warn" : "good" },
          { label: "receipt rows", value: counts.quick_scan_receipt_row_count as number | undefined },
          { label: "quant projection", value: String(searchQuantProjectionReceipt.status ?? "missing"), tone: searchQuantProjectionReceipt.symbol_valid === true ? "good" : "warn" },
          { label: "quant symbol", value: String(searchQuantProjectionReceipt.symbol ?? "--") },
          { label: "quant blockers", value: counts.search_quant_projection_production_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant rows", value: counts.search_quant_projection_row_count as number | undefined },
          { label: "quant activation", value: String(searchQuantProjectionActivation.status ?? "missing"), tone: searchQuantProjectionActivation.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "quant activation blockers", value: counts.search_quant_projection_activation_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_activation_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant dry-run", value: String(searchQuantProjectionAcceptanceDryRun.status ?? "missing"), tone: searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true ? "good" : "warn" },
          { label: "dry-run blockers", value: counts.search_quant_projection_acceptance_dry_run_blocking_count as number | undefined, tone: Number(counts.search_quant_projection_acceptance_dry_run_blocking_count ?? 0) ? "warn" : "good" },
          { label: "credential missing", value: counts.search_quant_projection_acceptance_credential_missing_count as number | undefined, tone: Number(counts.search_quant_projection_acceptance_credential_missing_count ?? 0) ? "warn" : "good" },
          { label: "quant request", value: String(searchQuantProjectionExecutionRequest.status ?? "missing"), tone: searchQuantProjectionExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "quant request blockers", value: counts.search_quant_projection_execution_request_local_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_execution_request_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant request prod", value: counts.search_quant_projection_execution_request_production_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_execution_request_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "provider coverage", value: String(providerParityDryRun.status ?? "missing"), tone: providerParityDryRun.ready_for_user_approved_provider_parity === true ? "good" : "warn" },
          { label: "coverage blockers", value: counts.provider_parity_dry_run_blocking_count as number | undefined, tone: Number(counts.provider_parity_dry_run_blocking_count ?? 0) ? "warn" : "good" },
          { label: "coverage symbols", value: counts.provider_parity_candidate_symbol_count as number | undefined },
          { label: "coverage credential", value: counts.provider_parity_credential_missing_count as number | undefined, tone: Number(counts.provider_parity_credential_missing_count ?? 0) ? "warn" : "good" },
          { label: "fast readiness", value: String(fastScanReadinessAudit.status ?? "missing"), tone: fastScanReadinessAudit.local_fast_scan_ready === true ? "good" : "warn" },
          { label: "fast blockers", value: counts.fast_scan_readiness_blocker_count as number | undefined, tone: Number(counts.fast_scan_readiness_blocker_count ?? 0) ? "bad" : "good" },
          { label: "no-loss QA", value: String(noFeatureLossAcceptance.status ?? "missing"), tone: noFeatureLossAcceptance.local_no_feature_loss_contract_ready === true ? "good" : "warn" },
          { label: "no-loss gaps", value: counts.no_feature_loss_visible_gap_count as number | undefined, tone: Number(counts.no_feature_loss_visible_gap_count ?? 0) ? "warn" : "good" },
          { label: "radar prod blockers", value: counts.no_feature_loss_production_blocker_count as number | undefined, tone: Number(counts.no_feature_loss_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "retire gate", value: String(replacementGapTriage.status ?? "missing"), tone: replacementGapTriage.legacy_retirement_ready === true ? "good" : "warn" },
          { label: "retire blockers", value: counts.replacement_gap_triage_blocking_count as number | undefined, tone: Number(counts.replacement_gap_triage_blocking_count ?? 0) ? "warn" : "good" },
          { label: "critical gaps", value: counts.replacement_gap_triage_critical_count as number | undefined, tone: Number(counts.replacement_gap_triage_critical_count ?? 0) ? "bad" : "good" },
          { label: "promotion gate", value: String(promotionBlockerAudit.status ?? "missing"), tone: promotionBlockerAudit.promotion_ready === true ? "good" : "warn" },
          { label: "promotion blockers", value: counts.candidate_radar_promotion_blocking_count as number | undefined, tone: Number(counts.candidate_radar_promotion_blocking_count ?? 0) ? "warn" : "good" },
          { label: "provider blockers", value: counts.candidate_radar_promotion_provider_blocker_count as number | undefined, tone: Number(counts.candidate_radar_promotion_provider_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker blockers", value: counts.candidate_radar_promotion_worker_blocker_count as number | undefined, tone: Number(counts.candidate_radar_promotion_worker_blocker_count ?? 0) ? "warn" : "good" },
          { label: "activation receipt", value: String(activationReceipt.status ?? "missing"), tone: activationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "activation blockers", value: counts.candidate_radar_activation_blocker_count as number | undefined, tone: Number(counts.candidate_radar_activation_blocker_count ?? 0) ? "warn" : "good" },
          { label: "activation pending", value: counts.candidate_radar_activation_pending_evidence_count as number | undefined, tone: Number(counts.candidate_radar_activation_pending_evidence_count ?? 0) ? "warn" : "good" },
          { label: "next recipe", value: String(nextExecutionRecipe.status ?? "missing"), tone: nextExecutionRecipe.recipe_ready_for_user_fast_scan === true ? "good" : "warn" },
          { label: "recipe blockers", value: counts.candidate_radar_next_execution_blocker_count as number | undefined, tone: Number(counts.candidate_radar_next_execution_blocker_count ?? 0) ? "warn" : "good" },
          { label: "recipe pending", value: counts.candidate_radar_next_execution_production_pending_count as number | undefined, tone: Number(counts.candidate_radar_next_execution_production_pending_count ?? 0) ? "warn" : "good" },
          { label: "worker recipe", value: String(workerExecutionRecipe.status ?? "missing"), tone: workerExecutionRecipe.local_worker_execution_recipe_ready === true ? "good" : "warn" },
          { label: "worker recipe blockers", value: counts.candidate_radar_worker_execution_recipe_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_execution_recipe_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker request", value: String(workerExecutionRequest.status ?? "missing"), tone: workerExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "request blockers", value: counts.candidate_radar_worker_execution_request_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_execution_request_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "full fallback", value: String(fullPoolWorkerFallback.status ?? "missing"), tone: fullPoolWorkerFallback.local_worker_fallback_full_pool_done === true ? "good" : "warn" },
          { label: "full fallback blockers", value: counts.candidate_radar_full_pool_worker_fallback_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_full_pool_worker_fallback_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "deep fallback", value: String(deepScanWorkerFallback.status ?? "missing"), tone: deepScanWorkerFallback.local_worker_fallback_deep_scan_done === true ? "good" : "warn" },
          { label: "deep fallback blockers", value: counts.candidate_radar_deep_scan_worker_fallback_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_deep_scan_worker_fallback_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker runtime link", value: String(workerRuntimeLinkedEvidence.status ?? "missing"), tone: workerRuntimeLinkedEvidence.worker_runtime_local_evidence_linked === true ? "good" : "warn" },
          { label: "runtime link blockers", value: counts.candidate_radar_worker_runtime_link_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_runtime_link_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "replacement review", value: String(productionReplacementReview.status ?? "missing"), tone: productionReplacementReview.local_review_ready === true ? "good" : "warn" },
          { label: "review blockers", value: counts.candidate_radar_production_replacement_review_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_production_replacement_review_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "promotion dry-run", value: String(productionPromotionDryRun.status ?? "missing"), tone: productionPromotionDryRun.ready_for_local_promotion_review === true ? "good" : "warn" },
          { label: "promotion blockers", value: counts.candidate_radar_production_promotion_dry_run_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_production_promotion_dry_run_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "durable recipe", value: String(durableEvidenceRecipe.status ?? "missing"), tone: durableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable blockers", value: counts.candidate_radar_durable_evidence_blocker_count as number | undefined, tone: Number(counts.candidate_radar_durable_evidence_blocker_count ?? 0) ? "warn" : "good" },
          { label: "stage manifest", value: String(productionStageScopeManifest.status ?? "missing"), tone: productionStageScopeManifest.local_manifest_ready === true ? "good" : "warn" },
          { label: "stage direct", value: counts.candidate_radar_production_stage_scope_direct_evidence_count as number | undefined, tone: Number(counts.candidate_radar_production_stage_scope_direct_evidence_count ?? 0) ? "good" : "warn" },
          { label: "stage pending", value: counts.candidate_radar_production_stage_scope_pending_count as number | undefined, tone: Number(counts.candidate_radar_production_stage_scope_pending_count ?? 0) ? "warn" : "good" },
          { label: "delta clarity", value: String(resultDeltaClarity.status ?? "missing"), tone: resultDeltaClarity.local_result_delta_clarity_ready === true ? "good" : "warn" },
          { label: "delta gaps", value: counts.result_delta_clarity_visible_gap_count as number | undefined, tone: Number(counts.result_delta_clarity_visible_gap_count ?? 0) ? "warn" : "good" },
          { label: "delta pending", value: counts.result_delta_clarity_pending_count as number | undefined, tone: Number(counts.result_delta_clarity_pending_count ?? 0) ? "warn" : "good" },
          { label: "prev diff", value: resultDeltaClarity.previous_cache_diff_done === true ? "done" : "pending", tone: resultDeltaClarity.previous_cache_diff_done === true ? "good" : "warn" },
          { label: "browser QA", value: String(browserQaRunbook.status ?? "missing"), tone: browserQaRunbook.local_runbook_ready === true ? "good" : "warn" },
          { label: "QA matrix", value: browserQaRunbook.qa_matrix_count as number | undefined },
          { label: "visual QA done", value: browserQaRunbook.visual_qa_complete === true ? "done" : "pending", tone: browserQaRunbook.visual_qa_complete === true ? "bad" : "good" },
          { label: "radar QA evidence", value: String(browserQaEvidence.status ?? "missing"), tone: browserQaEvidence.local_browser_qa_evidence_found === true ? "good" : "warn" },
          { label: "radar QA rows", value: counts.candidate_browser_qa_evidence_row_count as number | undefined },
          { label: "motion coverage", value: browserQaEvidence.motion_viewport_coverage_complete === true ? "complete" : "missing", tone: browserQaEvidence.motion_viewport_coverage_complete === true ? "good" : "warn" },
          { label: "default viewports", value: browserQaEvidence.default_motion_viewport_count as number | undefined },
          { label: "reduced viewports", value: browserQaEvidence.reduced_motion_viewport_count as number | undefined },
          { label: "QA review rows", value: counts.candidate_browser_qa_evidence_review_required_count as number | undefined, tone: Number(counts.candidate_browser_qa_evidence_review_required_count ?? 0) ? "warn" : "good" },
          { label: "QA review", value: String(browserQaReview.status ?? "missing"), tone: browserQaReview.local_browser_qa_review_ready === true ? "good" : "warn" },
          { label: "review blockers", value: counts.candidate_browser_qa_review_blocking_count as number | undefined, tone: Number(counts.candidate_browser_qa_review_blocking_count ?? 0) ? "warn" : "good" },
          { label: "added", value: counts.result_delta_added_count as number | undefined },
          { label: "removed", value: counts.result_delta_removed_count as number | undefined },
          { label: "rank delta", value: counts.result_delta_rank_changed_count as number | undefined },
          { label: "priority explain", value: String(candidatePriorityExplanation.status ?? "missing"), tone: candidatePriorityExplanation.priority_explanation_is_not_trade_signal === true ? "good" : "warn" },
          { label: "explain gaps", value: counts.priority_explanation_gap_count as number | undefined, tone: Number(counts.priority_explanation_gap_count ?? 0) ? "warn" : "good" },
          { label: "data-gap visible", value: counts.priority_explanation_data_gap_visible_count as number | undefined, tone: Number(counts.priority_explanation_data_gap_visible_count ?? 0) ? "warn" : "good" },
          { label: "full replacement", value: fastScanReadinessAudit.production_radar_replacement_complete === true ? "完成" : "未完成", tone: fastScanReadinessAudit.production_radar_replacement_complete === true ? "bad" : "good" },
          { label: "universe", value: coverageDetail.universe_size as number | undefined },
          { label: "input rows", value: coverageDetail.candidate_input_count as number | undefined },
          { label: "display cap", value: coverageDetail.candidate_display_limit as number | undefined },
          { label: "truncated", value: coverageDetail.candidate_display_truncated_count as number | undefined, tone: Number(coverageDetail.candidate_display_truncated_count ?? 0) ? "warn" : "good" },
          { label: "worker needed", value: fastScanRuntimeBudget.large_universe_worker_required === true ? "yes" : "no", tone: fastScanRuntimeBudget.large_universe_worker_required === true ? "warn" : "good" },
          { label: "覆盖组", value: scanCoverage.mapped_signal_group_count as number | undefined },
          { label: "缺口组", value: scanCoverage.missing_signal_group_count as number | undefined, tone: scanCoverage.missing_signal_group_count ? "warn" : "good" },
          { label: "provider blocked", value: counts.provider_blocked_group_count as number | undefined, tone: counts.provider_blocked_group_count ? "warn" : "good" },
          { label: "stale inputs", value: counts.stale_input_group_count as number | undefined, tone: counts.stale_input_group_count ? "warn" : "good" },
          { label: "missing provider", value: counts.missing_provider_data_group_count as number | undefined, tone: counts.missing_provider_data_group_count ? "warn" : "good" },
          { label: "degraded modes", value: counts.degraded_mode_active_count as number | undefined, tone: counts.degraded_mode_active_count ? "warn" : "good" },
          { label: "coverage gap", value: counts.legacy_parity_gap_count as number | undefined, tone: counts.legacy_parity_gap_count ? "warn" : "good" },
          { label: "coverage mapped", value: counts.legacy_parity_mapped_count as number | undefined },
          { label: "coverage receipt", value: String(legacyParityAcceptanceReceipt.status ?? "missing"), tone: legacyParityAcceptanceReceipt.local_acceptance_receipt_ready === true ? "good" : "warn" },
          { label: "coverage blockers", value: counts.legacy_parity_acceptance_production_blocker_count as number | undefined, tone: Number(counts.legacy_parity_acceptance_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "coverage ready", value: counts.legacy_parity_acceptance_ready_count as number | undefined },
          { label: "跳过原因", value: scanCoverage.skipped_reason_count as number | undefined, tone: scanCoverage.skipped_reason_count ? "warn" : "good" },
          { label: "验收行", value: scanAcceptanceRows.length },
          { label: "freshness", value: String(freshnessState.state ?? "unknown"), tone: freshnessState.source === "missing" ? "warn" : "good" },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "市场扫描", value: policy.does_not_scan_market === true ? "不会" : "可能", tone: policy.does_not_scan_market === true ? "good" : "bad" },
          { label: "quick scan", value: policy.quick_scan_reads_cache_only === true ? "本地" : "未知", tone: policy.quick_scan_reads_cache_only === true ? "good" : "warn" },
          { label: "full-pool plan", value: String(fullPoolPlan.status ?? "missing"), tone: fullPoolPlan.status === "full_pool_plan_ready" ? "good" : "neutral" },
          { label: "local full-pool", value: String(fullPoolLocalExecutionReceipt.status ?? "missing"), tone: fullPoolLocalExecutionReceipt.local_full_pool_execution_done === true ? "good" : "warn" },
          { label: "local universe", value: counts.full_pool_local_execution_candidate_count as number | undefined },
          { label: "local prod blockers", value: counts.full_pool_local_execution_production_blocker_count as number | undefined, tone: Number(counts.full_pool_local_execution_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "full-pool done", value: fullPoolPlan.full_pool_scan_done === true ? "完成" : "未执行", tone: fullPoolPlan.full_pool_scan_done === true ? "bad" : "good" },
          { label: "full-pool blockers", value: fullPoolPlan.blocking_issue_count as number | undefined, tone: Number(fullPoolPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "deep-scan plan", value: String(deepScanPlan.status ?? "missing"), tone: deepScanPlan.status === "deep_scan_plan_ready" ? "good" : "neutral" },
          { label: "deep local review", value: String(deepScanLocalReviewReceipt.status ?? "missing"), tone: deepScanLocalReviewReceipt.local_deep_scan_review_done === true ? "good" : "warn" },
          { label: "deep review rows", value: counts.deep_scan_local_review_candidate_count as number | undefined },
          { label: "deep prod blockers", value: counts.deep_scan_local_review_production_blocker_count as number | undefined, tone: Number(counts.deep_scan_local_review_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "deep-scan done", value: deepScanPlan.deep_scan_done === true ? "完成" : "未执行", tone: deepScanPlan.deep_scan_done === true ? "bad" : "good" },
          { label: "deep blockers", value: deepScanPlan.blocking_issue_count as number | undefined, tone: Number(deepScanPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "feature gaps", value: deepScanPlan.legacy_feature_gap_count as number | undefined, tone: Number(deepScanPlan.legacy_feature_gap_count ?? 0) ? "warn" : "good" },
          { label: "local pool", value: localPoolAudit.normalized_candidate_count as number | undefined },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
          ]}
        />
      </details>

      <details className="developer-audit-details">
        <summary>扫描覆盖 / 验收审计</summary>
        <PacketCard title="旧雷达信号组覆盖" subtitle="legacy_signal_group_rows；缺口只报告，不静默降能" status={String(scanCoverage.coverage_status ?? "coverage")}>
          <DataLineageTable rows={legacySignalRows} />
        </PacketCard>

        <PacketCard title="扫描覆盖明细" subtitle="coverage_detail_summary / provider_coverage_rows / degraded_mode_rows；缺失不静默降能" status={String(coverageDetail.degraded_mode_active ? "degraded" : "coverage")}>
          <p>universe size、provider-blocked groups、stale inputs、missing provider data 和 degraded modes 必须显式展示；页面渲染不会补数或触发 full-pool scan。</p>
          <p>missing provider data is reported, not dropped；quick scan 仍是 research-only，不替代 legacy full scan。</p>
          <DataLineageTable rows={objectRow(coverageDetail)} />
          <DataLineageTable rows={providerCoverageRows} />
          <DataLineageTable rows={degradedModeRows} />
        </PacketCard>

        <PacketCard title="扫描执行验收" subtitle="scan_execution_summary / scan_acceptance_rows；区分 cache、local scan 和 plan-only" status={String(scanExecutionSummary.scan_family ?? "audit")}>
          <p>scan_execution_summary 只总结本地执行边界，不证明 full-pool scan 已完成。</p>
          <p>scan_acceptance_rows 把 provider gap、freshness、local pool、full-pool 和交易隔离逐项展示。</p>
          <DataLineageTable rows={objectRow(scanExecutionSummary)} />
          <DataLineageTable rows={scanAcceptanceRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>快扫回执 / 流水线审计</summary>
        <PacketCard title="快扫执行回执" subtitle="quick_scan_execution_receipt；把本次 cache/quick/watchlist/custom scan 的覆盖、截断和阻断项集中展示" status={String(quickScanReceipt.status ?? "missing")}>
          <p>local_quick_scan_receipt_ready: {String(quickScanReceipt.local_quick_scan_receipt_ready === true)}</p>
          <p>scan_mode: {String(quickScanReceipt.scan_mode ?? "--")}；scan_family: {String(quickScanReceipt.scan_family ?? "--")}；writes_sqlite_packet: {String(quickScanReceipt.writes_sqlite_packet === true)}</p>
          <p>candidate_input_count: {String(quickScanReceipt.candidate_input_count ?? 0)}；candidate_row_count: {String(quickScanReceipt.candidate_row_count ?? 0)}；truncated: {String(quickScanReceipt.candidate_display_truncated_count ?? 0)}</p>
          <p>provider_gap_count: {String(quickScanReceipt.provider_gap_count ?? 0)}；missing_signal_group_count: {String(quickScanReceipt.missing_signal_group_count ?? 0)}；freshness: {String(quickScanReceipt.freshness_source ?? "missing")}:{String(quickScanReceipt.freshness_state ?? "unknown")}</p>
          <p>production_radar_replacement_complete: {String(quickScanReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(quickScanReceipt.legacy_retirement_ready === true)}；provider_backed_acceptance_done: {String(quickScanReceipt.provider_backed_acceptance_done === true)}</p>
          <p>这个回执是本地可见性证明：它说明快扫没有静默降能、没有外联、没有改 action；它不等于 full-pool、deep-scan、provider-backed 或浏览器性能验收完成。</p>
          <DataLineageTable rows={objectRow(quickScanReceipt)} />
          <DataLineageTable rows={quickScanReceiptRows} />
        </PacketCard>

        <PacketCard title="快扫任务流水线合同" subtitle="fast_scan_task_pipeline_contract；证明先渲染 cache，再通过 POST task 快扫，失败和缺口都可见" status={String(fastScanTaskPipeline.status ?? "missing")}>
          <p>local_task_pipeline_ready: {String(fastScanTaskPipeline.local_task_pipeline_ready === true)}</p>
          <p>initial_render_nonblocking: {String(fastScanTaskPipeline.initial_render_nonblocking === true)}；post_task_boundary_visible: {String(fastScanTaskPipeline.post_task_boundary_visible === true)}</p>
          <p>task_id_visible: {String(fastScanTaskPipeline.task_id_visible === true)}；task_status_panel_required: {String(fastScanTaskPipeline.task_status_panel_required === true)}</p>
          <p>last_success_cache_fallback_visible: {String(fastScanTaskPipeline.last_success_cache_fallback_visible === true)}；safe_failure_boundary_visible: {String(fastScanTaskPipeline.safe_failure_boundary_visible === true)}</p>
          <p>async_worker_execution_done: {String(fastScanTaskPipeline.async_worker_execution_done === true)}；provider_backed_acceptance_done: {String(fastScanTaskPipeline.provider_backed_acceptance_done === true)}；production_radar_replacement_complete: {String(fastScanTaskPipeline.production_radar_replacement_complete === true)}</p>
          <p>这个合同只证明 3.0 本地快扫流水线形状：页面不等待扫描、按钮发起 POST task、TaskStatusPanel 轮询状态、上次 cache 仍可读、输入预算和 feature gap 可见；它不是 worker 全量扫描、provider-backed coverage、浏览器性能或生产替代完成。</p>
          <DataLineageTable rows={objectRow(fastScanTaskPipeline)} />
          <DataLineageTable rows={fastScanTaskPipelineRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>快扫质量审计</summary>
        <PacketCard title="快扫运行预算" subtitle="fast_scan_runtime_budget_contract；控制同步展示规模，超限必须可见并转 worker" status={String(fastScanRuntimeBudget.status ?? "missing")}>
          <p>display_candidate_limit: {String(fastScanRuntimeBudget.display_candidate_limit ?? "--")}</p>
          <p>candidate_input_count: {String(fastScanRuntimeBudget.candidate_input_count ?? 0)}</p>
          <p>candidate_display_truncated_count: {String(fastScanRuntimeBudget.candidate_display_truncated_count ?? 0)}</p>
          <p>large_universe_worker_required: {String(fastScanRuntimeBudget.large_universe_worker_required ?? false)}</p>
          <p>browser_performance_trace_done: {String(fastScanRuntimeBudget.browser_performance_trace_done ?? false)}</p>
          <p>快扫预算只限制本地同步展示和输入规范化；超出时报告截断与 worker 边界，不隐藏 provider、freshness 或 retained coverage 缺口。</p>
          <DataLineageTable rows={objectRow(fastScanRuntimeBudget)} />
          <DataLineageTable rows={fastScanRuntimeBudgetRows} />
        </PacketCard>

        <PacketCard title="快扫 readiness 审计" subtitle="fast_scan_readiness_audit / rows；证明本地快扫不阻塞、不静默降能，但不代表 full-pool/deep-scan 完成" status={String(fastScanReadinessAudit.status ?? "missing")}>
          <p>local_fast_scan_ready: {String(fastScanReadinessAudit.local_fast_scan_ready ?? false)}</p>
          <p>production_radar_replacement_complete: {String(fastScanReadinessAudit.production_radar_replacement_complete ?? false)}</p>
          <p>provider_backed_acceptance_done: {String(fastScanReadinessAudit.provider_backed_acceptance_done ?? false)}</p>
          <p>full_pool_scan_done: {String(fastScanReadinessAudit.full_pool_scan_done ?? false)}</p>
          <p>deep_scan_done: {String(fastScanReadinessAudit.deep_scan_done ?? false)}</p>
          <DataLineageTable rows={objectRow(fastScanReadinessAudit)} />
          <DataLineageTable rows={fastScanReadinessRows} />
        </PacketCard>

        <PacketCard title="快扫不降能验收" subtitle="no_feature_loss_acceptance_contract；本地 QA 面可见，但不是生产雷达替代完成" status={String(noFeatureLossAcceptance.status ?? "missing")}>
          <p>local_no_feature_loss_contract_ready: {String(noFeatureLossAcceptance.local_no_feature_loss_contract_ready ?? false)}</p>
          <p>production_radar_replacement_complete: {String(noFeatureLossAcceptance.production_radar_replacement_complete ?? false)}</p>
          <p>legacy_fallback_required: {String(noFeatureLossAcceptance.legacy_fallback_required ?? true)}</p>
          <p>browser_performance_trace_done: {String(noFeatureLossAcceptance.browser_performance_trace_done ?? false)}</p>
          <p>此合同汇总旧信号组、输出字段、provider/freshness 缺口、运行预算、full-pool/deep-scan 边界和交易隔离；gap 可见不等于真实 full-pool/deep-scan/provider-backed 验收完成。</p>
          <DataLineageTable rows={objectRow(noFeatureLossAcceptance)} />
          <DataLineageTable rows={noFeatureLossAcceptanceRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>生产替代 / 退场审计</summary>
        <PacketCard title="旧雷达退场缺口分诊" subtitle="replacement_gap_triage_contract；分清 critical、pending 和已通过项，仍不是生产替代完成" status={String(replacementGapTriage.status ?? "missing")}>
          <p>legacy_retirement_ready: {String(replacementGapTriage.legacy_retirement_ready ?? false)}</p>
          <p>blocking_gap_count: {String(replacementGapTriage.blocking_gap_count ?? 0)}；critical_gap_count: {String(replacementGapTriage.critical_gap_count ?? 0)}；pending_gap_count: {String(replacementGapTriage.pending_gap_count ?? 0)}</p>
          <p>此分诊只读取本地合同，把旧信号组、输出字段、provider、freshness、浏览器视觉 QA、性能 trace、full/deep worker 执行和交易隔离分层显示；不能当作 full-pool/deep-scan 或 provider-backed 验收。</p>
          <DataLineageTable rows={objectRow(replacementGapTriage)} />
          <DataLineageTable rows={replacementGapTriageRows} />
        </PacketCard>

        <PacketCard title="雷达生产替代阻断审计" subtitle="candidate_radar_promotion_blocker_audit；列出 quick radar 升级为生产替代前必须清掉的阻断项" status={String(promotionBlockerAudit.status ?? "missing")}>
          <p>local_promotion_audit_ready: {String(promotionBlockerAudit.local_promotion_audit_ready === true)}</p>
          <p>promotion_ready: {String(promotionBlockerAudit.promotion_ready === true)}；production_radar_replacement_complete: {String(promotionBlockerAudit.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(promotionBlockerAudit.legacy_retirement_ready === true)}</p>
          <p>blocking_promotion_count: {String(promotionBlockerAudit.blocking_promotion_count ?? 0)}；provider_acceptance_blocker_count: {String(promotionBlockerAudit.provider_acceptance_blocker_count ?? 0)}；worker_execution_blocker_count: {String(promotionBlockerAudit.worker_execution_blocker_count ?? 0)}；browser_evidence_blocker_count: {String(promotionBlockerAudit.browser_evidence_blocker_count ?? 0)}</p>
          <p>full_pool_scan_done: {String(promotionBlockerAudit.full_pool_scan_done === true)}；deep_scan_done: {String(promotionBlockerAudit.deep_scan_done === true)}；provider_backed_acceptance_done: {String(promotionBlockerAudit.provider_backed_acceptance_done === true)}</p>
          <p>此审计只读本地 cache 和合同，把 full-pool、deep-scan、provider-backed、browser QA、freshness 与交易隔离的生产阻断项集中显示；它不会运行扫描、不会调用 provider/model、不会解除旧雷达 fallback。</p>
          <DataLineageTable rows={objectRow(promotionBlockerAudit)} />
          <DataLineageTable rows={promotionBlockerRows} />
        </PacketCard>

        <PacketCard title="雷达生产化激活收据" subtitle="candidate_radar_production_activation_receipt；统一说明下一步可执行验收和仍缺的生产证据" status={String(activationReceipt.status ?? "missing")}>
          <p>local_activation_receipt_ready: {String(activationReceipt.local_activation_receipt_ready === true)}</p>
          <p>allowed_next_step: {String(activationReceipt.allowed_next_step ?? "--")}</p>
          <p>production_radar_replacement_complete: {String(activationReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(activationReceipt.legacy_retirement_ready === true)}</p>
          <p>full_pool_scan_done: {String(activationReceipt.full_pool_scan_done === true)}；deep_scan_done: {String(activationReceipt.deep_scan_done === true)}；provider_backed_acceptance_done: {String(activationReceipt.provider_backed_acceptance_done === true)}</p>
          <p>pending_evidence_count: {String(activationReceipt.pending_evidence_count ?? 0)}；production_blocker_count: {String(activationReceipt.production_blocker_count ?? 0)}</p>
          <p>此收据只把 full-pool worker、deep-scan worker、provider-backed coverage、browser visual/performance 和 legacy retirement 证据串成下一步清单；它不会运行扫描、不会调用 provider/model、不会把候选变成买入指令。</p>
          <DataLineageTable rows={objectRow(activationReceipt)} />
          <DataLineageTable rows={activationReceiptRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>执行配方 / worker 申请审计</summary>
        <PacketCard title="雷达下一步执行配方" subtitle="candidate_radar_next_execution_recipe；快扫优先，不降能证据可见，生产替代仍需后续验收" status={String(nextExecutionRecipe.status ?? "missing")}>
          <p>recipe_ready_for_user_fast_scan: {String(nextExecutionRecipe.recipe_ready_for_user_fast_scan === true)}</p>
          <p>allowed_next_step: {String(nextExecutionRecipe.allowed_next_step ?? "resolve_local_candidate_radar_fast_scan_blockers")}</p>
          <p>recommended_fast_scan_route: {String(nextExecutionRecipe.recommended_fast_scan_route ?? "POST /api/candidate-radar/scan-quick")}</p>
          <p>recommended_full_pool_local_route: {String(nextExecutionRecipe.recommended_full_pool_local_route ?? "POST /api/candidate-radar/full-pool-local-scan")}；recommended_deep_scan_local_review_route: {String(nextExecutionRecipe.recommended_deep_scan_local_review_route ?? "POST /api/candidate-radar/deep-scan-local-review")}</p>
          <p>recommended_worker_full_pool_route: {String(nextExecutionRecipe.recommended_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")}；recommended_worker_deep_scan_route: {String(nextExecutionRecipe.recommended_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
          <p>provider/model/browser 验收路线: {String(nextExecutionRecipe.provider_parity_dry_run_route ?? "POST /api/candidate-radar/provider-parity-dry-run")} / {String(nextExecutionRecipe.quant_projection_acceptance_dry_run_route ?? "POST /api/candidate-radar/quant-projection-acceptance-dry-run")} / {String(nextExecutionRecipe.quant_projection_execution_request_route ?? "POST /api/candidate-radar/quant-projection-execution-request")} / {String(nextExecutionRecipe.browser_qa_review_route ?? "POST /api/candidate-radar/browser-qa-review")}</p>
          <p>ready_to_execute_from_cache: {String(nextExecutionRecipe.ready_to_execute_from_cache === true)}；worker_execution_recipe_ready: {String(nextExecutionRecipe.worker_execution_recipe_ready === true)}；worker_execution_implemented: {String(nextExecutionRecipe.worker_execution_implemented === true)}</p>
          <p>production_radar_replacement_complete: {String(nextExecutionRecipe.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(nextExecutionRecipe.legacy_retirement_ready === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(nextExecutionRecipe.tushare_called === true)} / {String(nextExecutionRecipe.deepseek_called === true)} / {String(nextExecutionRecipe.github_called === true)}</p>
          <p>not_allowed_next_steps: {Array.isArray(nextExecutionRecipe.not_allowed_next_steps) ? nextExecutionRecipe.not_allowed_next_steps.join(" / ") : "scan from render / quick scan as production replacement / provider/model calls from render / candidate rows as buy instructions / retire legacy fallback early"}</p>
          <DataLineageTable rows={objectRow(nextExecutionRecipe)} />
          <DataLineageTable rows={nextExecutionRecipeRows} />
        </PacketCard>

        <PacketCard title="雷达 worker 执行配方" subtitle="candidate_radar_worker_execution_recipe；全池/深扫的 future worker 验收路线，不启动 worker、不调用 provider/model" status={String(workerExecutionRecipe.status ?? "missing")}>
          <p>local_worker_execution_recipe_ready: {String(workerExecutionRecipe.local_worker_execution_recipe_ready === true)}</p>
          <p>worker_execution_scope_hash_short: {String(workerExecutionRecipe.worker_execution_scope_hash_short ?? "--")}</p>
          <p>recommended_worker_full_pool_route: {String(workerExecutionRecipe.recommended_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")}</p>
          <p>recommended_worker_deep_scan_route: {String(workerExecutionRecipe.recommended_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
          <p>worker_task_created / worker_execution_implemented: {String(workerExecutionRecipe.worker_task_created === true)} / {String(workerExecutionRecipe.worker_execution_implemented === true)}</p>
          <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(workerExecutionRecipe.full_pool_scan_done === true)} / {String(workerExecutionRecipe.deep_scan_done === true)} / {String(workerExecutionRecipe.provider_backed_acceptance_done === true)}</p>
          <p>required_storage_datasets: {Array.isArray(workerExecutionRecipe.required_storage_datasets) ? workerExecutionRecipe.required_storage_datasets.join(" / ") : "daily / daily_basic / moneyflow / trade_cal"}</p>
          <p>not_allowed_next_steps: {Array.isArray(workerExecutionRecipe.not_allowed_next_steps) ? workerExecutionRecipe.not_allowed_next_steps.join(" / ") : "start worker from render / treat recipe as execution done / retire legacy early"}</p>
          <p>tushare_called / deepseek_called / github_called: {String(workerExecutionRecipe.tushare_called === true)} / {String(workerExecutionRecipe.deepseek_called === true)} / {String(workerExecutionRecipe.github_called === true)}</p>
          <DataLineageTable rows={objectRow(workerExecutionRecipe)} />
          <DataLineageTable rows={workerExecutionRows} />
        </PacketCard>

        <PacketCard title="雷达 worker 执行申请" subtitle="POST /api/candidate-radar/worker-execution-request；绑定 worker recipe hash，不启动 worker、不执行全池/深扫" status={String(workerExecutionRequest.status ?? "missing")}>
          <div className="actions">
            <button
              onClick={launchWorkerExecutionRequest}
              disabled={!workerExecutionRecipe.worker_execution_scope_hash}
              title={workerExecutionRecipe.worker_execution_scope_hash ? "绑定 worker recipe hash；不启动 worker" : "先等待 worker execution recipe scope hash"}
              aria-label="create worker execution request after worker recipe scope hash"
            >
              生成 worker execution request
            </button>
          </div>
          <p>local_execution_request_ready: {String(workerExecutionRequest.local_execution_request_ready === true)}；ready_for_manual_worker_task_submission: {String(workerExecutionRequest.ready_for_manual_worker_task_submission === true)}</p>
          <p>requested hash matches latest: {String(workerExecutionRequest.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(workerExecutionRequest.worker_execution_scope_hash_short ?? "--")}</p>
          <p>local full-pool / deep review / provider coverage: {String(workerExecutionRequest.local_full_pool_receipt_visible === true)} / {String(workerExecutionRequest.local_deep_scan_review_visible === true)} / {String(workerExecutionRequest.provider_parity_scope_ticket_visible === true)}</p>
          <p>quant projection scope visible: {String(workerExecutionRequest.quant_projection_scope_ticket_visible === true)}</p>
          <p>target: {String(workerExecutionRequest.target_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")} / {String(workerExecutionRequest.target_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
          <p>worker_task_created / worker_task_executed / worker_started: {String(workerExecutionRequest.worker_task_created === true)} / {String(workerExecutionRequest.worker_task_executed === true)} / {String(workerExecutionRequest.worker_started === true)}</p>
          <p>full_pool_scan_done / deep_scan_done / production_replacement: {String(workerExecutionRequest.full_pool_scan_done === true)} / {String(workerExecutionRequest.deep_scan_done === true)} / {String(workerExecutionRequest.production_radar_replacement_complete === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(workerExecutionRequest.tushare_called === true)} / {String(workerExecutionRequest.deepseek_called === true)} / {String(workerExecutionRequest.github_called === true)}</p>
          <p>not_allowed_next_steps: {Array.isArray(workerExecutionRequest.not_allowed_next_steps) ? workerExecutionRequest.not_allowed_next_steps.join(" / ") : "create worker task / start worker / run full-pool or deep-scan / call provider/model / retire legacy fallback"}</p>
          <DataLineageTable rows={objectRow(workerExecutionRequest)} />
          <DataLineageTable rows={workerExecutionRequestRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>worker fallback / runtime 审计</summary>
        <PacketCard title="Full-pool worker fallback" subtitle="POST /api/candidate-radar/full-pool-worker-scan；显式按钮触发的本地 worker-shaped fallback，不启动 Redis/Celery" status={String(fullPoolWorkerFallback.status ?? "missing")}>
          <div className="actions">
            <button
              onClick={launchFullPoolWorkerFallback}
              disabled={!workerExecutionRequest.worker_execution_scope_hash}
              title={workerExecutionRequest.worker_execution_scope_hash ? "运行本地 full-pool worker-shaped fallback；不启动 Redis/Celery" : "先生成 worker execution request scope hash"}
              aria-label="run full pool worker fallback after worker execution request scope hash"
            >
              运行 full-pool worker fallback
            </button>
          </div>
          <p>local_worker_fallback_full_pool_done: {String(fullPoolWorkerFallback.local_worker_fallback_full_pool_done === true)}；ready_for_worker_runtime_promotion: {String(fullPoolWorkerFallback.ready_for_worker_runtime_promotion === true)}</p>
          <p>scope match: {String(fullPoolWorkerFallback.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(fullPoolWorkerFallback.worker_execution_scope_hash_short ?? "--")}</p>
          <p>candidate_row_count: {String(fullPoolWorkerFallback.candidate_row_count ?? 0)}；local_blocker_count / production_blocker_count: {String(fullPoolWorkerFallback.local_blocker_count ?? 0)} / {String(fullPoolWorkerFallback.production_blocker_count ?? 0)}</p>
          <p>worker_started / celery_worker_started / redis_broker_used: {String(fullPoolWorkerFallback.worker_started === true)} / {String(fullPoolWorkerFallback.celery_worker_started === true)} / {String(fullPoolWorkerFallback.redis_broker_used === true)}</p>
          <p>production_full_pool_scan_done / provider_backed_acceptance_done / legacy_retirement_ready: {String(fullPoolWorkerFallback.production_full_pool_scan_done === true)} / {String(fullPoolWorkerFallback.provider_backed_acceptance_done === true)} / {String(fullPoolWorkerFallback.legacy_retirement_ready === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(fullPoolWorkerFallback.tushare_called === true)} / {String(fullPoolWorkerFallback.deepseek_called === true)} / {String(fullPoolWorkerFallback.github_called === true)}</p>
          <DataLineageTable rows={objectRow(fullPoolWorkerFallback)} />
          <DataLineageTable rows={fullPoolWorkerFallbackRows} />
        </PacketCard>

        <PacketCard title="Deep-scan worker fallback" subtitle="POST /api/candidate-radar/deep-scan-worker；消费本地 deep-scan review，不启动 Redis/Celery/DeepSeek" status={String(deepScanWorkerFallback.status ?? "missing")}>
          <div className="actions">
            <button
              onClick={launchDeepScanWorkerFallback}
              disabled={!workerExecutionRequest.worker_execution_scope_hash}
              title={workerExecutionRequest.worker_execution_scope_hash ? "运行本地 deep-scan worker-shaped fallback；不调用 DeepSeek" : "先生成 worker execution request scope hash"}
              aria-label="run deep scan worker fallback after worker execution request scope hash"
            >
              运行 deep-scan worker fallback
            </button>
          </div>
          <p>local_worker_fallback_deep_scan_done: {String(deepScanWorkerFallback.local_worker_fallback_deep_scan_done === true)}；ready_for_worker_runtime_promotion: {String(deepScanWorkerFallback.ready_for_worker_runtime_promotion === true)}</p>
          <p>scope match: {String(deepScanWorkerFallback.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(deepScanWorkerFallback.worker_execution_scope_hash_short ?? "--")}</p>
          <p>candidate_row_count: {String(deepScanWorkerFallback.candidate_row_count ?? 0)}；local_blocker_count / production_blocker_count: {String(deepScanWorkerFallback.local_blocker_count ?? 0)} / {String(deepScanWorkerFallback.production_blocker_count ?? 0)}</p>
          <p>worker_started / celery_worker_started / redis_broker_used: {String(deepScanWorkerFallback.worker_started === true)} / {String(deepScanWorkerFallback.celery_worker_started === true)} / {String(deepScanWorkerFallback.redis_broker_used === true)}</p>
          <p>production_deep_scan_done / deepseek_model_ledger_complete / legacy_retirement_ready: {String(deepScanWorkerFallback.production_deep_scan_done === true)} / {String(deepScanWorkerFallback.deepseek_model_ledger_complete === true)} / {String(deepScanWorkerFallback.legacy_retirement_ready === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(deepScanWorkerFallback.tushare_called === true)} / {String(deepScanWorkerFallback.deepseek_called === true)} / {String(deepScanWorkerFallback.github_called === true)}</p>
          <DataLineageTable rows={objectRow(deepScanWorkerFallback)} />
          <DataLineageTable rows={deepScanWorkerFallbackRows} />
        </PacketCard>

        <PacketCard title="雷达 worker runtime link" subtitle="candidate_radar_worker_runtime_linked_evidence；只读连接 LTG-06 本地 runtime QA 证据，不启动 worker、不外联" status={String(workerRuntimeLinkedEvidence.status ?? "missing")}>
          <p>worker_runtime_local_evidence_linked: {String(workerRuntimeLinkedEvidence.worker_runtime_local_evidence_linked === true)}；direct layer: {String(workerRuntimeLinkedEvidence.worker_runtime_direct_evidence_layer ?? "--")}</p>
          <p>source packet: {String(workerRuntimeLinkedEvidence.source_packet_key ?? "command_center_3_worker_runtime_qa_execution_packet")}；read status: {String(workerRuntimeLinkedEvidence.source_packet_read_status ?? "missing")}</p>
          <p>execution task: {String(workerRuntimeLinkedEvidence.worker_runtime_execution_task_id ?? "--")}；runtime scope: {String(workerRuntimeLinkedEvidence.worker_runtime_qa_scope_hash_short ?? "--")}</p>
          <p>local fallback / task log / append-only / cross-process: {String(workerRuntimeLinkedEvidence.local_fallback_round_trip_verified === true)} / {String(workerRuntimeLinkedEvidence.task_log_round_trip_verified === true)} / {String(workerRuntimeLinkedEvidence.append_only_worker_log_verified === true)} / {String(workerRuntimeLinkedEvidence.cross_process_task_control_verified === true)}</p>
          <p>scheduler off / provider-model no autoschedule / no-trade: {String(workerRuntimeLinkedEvidence.scheduler_default_off_runtime_verified === true)} / {String(workerRuntimeLinkedEvidence.provider_model_no_autoschedule_boundary_verified === true)} / {String(workerRuntimeLinkedEvidence.no_trade_no_action_boundary_verified === true)}</p>
          <p>production worker / radar replacement / provider-backed: {String(workerRuntimeLinkedEvidence.production_worker_complete === true)} / {String(workerRuntimeLinkedEvidence.production_radar_replacement_complete === true)} / {String(workerRuntimeLinkedEvidence.provider_backed_acceptance_done === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(workerRuntimeLinkedEvidence.tushare_called === true)} / {String(workerRuntimeLinkedEvidence.deepseek_called === true)} / {String(workerRuntimeLinkedEvidence.github_called === true)}</p>
          <p>这个 link 只证明已有 LTG-06 本地 runtime QA 证据可被雷达迁移审查看见；真实 Redis/Celery worker、全池/深扫、provider coverage、browser promotion 和 legacy retirement 仍未完成。</p>
          <DataLineageTable rows={objectRow(workerRuntimeLinkedEvidence)} />
          <DataLineageTable rows={workerRuntimeLinkedRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>生产替代 review / promotion 审计</summary>
        <PacketCard title="雷达生产替代审查" subtitle="POST /api/candidate-radar/production-replacement-review；汇总快扫、不降能、worker/provider/browser 缺口，不执行外部任务" status={String(productionReplacementReview.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchProductionReplacementReview}>生成 production replacement review</button>
        </div>
        <p>local_review_ready: {String(productionReplacementReview.local_review_ready === true)}；ready_for_production_replacement: {String(productionReplacementReview.ready_for_production_replacement === true)}</p>
        <p>production_radar_replacement_complete: {String(productionReplacementReview.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(productionReplacementReview.legacy_retirement_ready === true)}；legacy_fallback_required: {String(productionReplacementReview.legacy_fallback_required !== false)}</p>
        <p>fast_scan_ready: {String(productionReplacementReview.fast_scan_ready === true)}；no_feature_loss_local_surface_ready: {String(productionReplacementReview.no_feature_loss_local_surface_ready === true)}；legacy_parity_receipt_ready: {String(productionReplacementReview.legacy_parity_receipt_ready === true)}</p>
        <p>local full/deep/full fallback/deep fallback: {String(productionReplacementReview.local_full_pool_receipt_visible === true)} / {String(productionReplacementReview.local_deep_scan_review_visible === true)} / {String(productionReplacementReview.full_pool_worker_fallback_visible === true)} / {String(productionReplacementReview.deep_scan_worker_fallback_visible === true)}；provider scope / worker request / quant request / browser review: {String(productionReplacementReview.provider_parity_scope_ticket_visible === true)} / {String(productionReplacementReview.worker_execution_request_visible === true)} / {String(productionReplacementReview.quant_projection_execution_request_visible === true)} / {String(productionReplacementReview.browser_qa_review_visible === true)}</p>
        <p>worker full/deep / provider backed / DeepSeek ledger / browser promoted: {String(productionReplacementReview.worker_full_pool_execution_done === true)} / {String(productionReplacementReview.worker_deep_scan_execution_done === true)} / {String(productionReplacementReview.provider_backed_acceptance_done === true)} / {String(productionReplacementReview.deepseek_model_ledger_complete === true)} / {String(productionReplacementReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionReplacementReview.local_blocker_count ?? 0)} / {String(productionReplacementReview.production_blocker_count ?? 0)}；review_scope_hash_short: {String(productionReplacementReview.review_scope_hash_short ?? "--")}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionReplacementReview.tushare_called === true)} / {String(productionReplacementReview.deepseek_called === true)} / {String(productionReplacementReview.github_called === true)}</p>
        <p>这个审查只把 3.0 雷达迁移能不能退旧模块讲清楚：本地快扫可以 ready，但生产替代仍要真实 worker 全池/深扫、provider call ledger、可选 DeepSeek model ledger、浏览器性能和 legacy retirement review。</p>
        <DataLineageTable rows={objectRow(productionReplacementReview)} />
        <DataLineageTable rows={productionReplacementReviewRows} />
        </PacketCard>

        <PacketCard title="雷达 production promotion dry-run" subtitle="POST /api/candidate-radar/production-promotion-dry-run；绑定 replacement review scope，不运行 worker/provider/model/browser" status={String(productionPromotionDryRun.status ?? "missing")}>
        <div className="actions">
          <button
            onClick={launchProductionPromotionDryRun}
            disabled={!productionReplacementReview.review_scope_hash}
            title={productionReplacementReview.review_scope_hash ? "绑定 replacement review scope；不运行 worker/provider/model/browser" : "先生成 production replacement review scope hash"}
            aria-label="create production promotion dry run after replacement review scope hash"
          >
            生成 production promotion dry-run
          </button>
        </div>
        <p>ready_for_local_promotion_review: {String(productionPromotionDryRun.ready_for_local_promotion_review === true)}；ready_to_mark_production: {String(productionPromotionDryRun.ready_to_mark_production_radar_replacement_complete === true)}</p>
        <p>review scope match: {String(productionPromotionDryRun.requested_review_scope_hash_matches_latest === true)}；review scope: {String(productionPromotionDryRun.production_replacement_review_scope_hash_short ?? "--")}；promotion scope: {String(productionPromotionDryRun.promotion_scope_hash_short ?? "--")}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionPromotionDryRun.local_blocker_count ?? 0)} / {String(productionPromotionDryRun.production_blocker_count ?? 0)}</p>
        <p>worker full/deep / provider / DeepSeek ledger: {String(productionPromotionDryRun.worker_full_pool_execution_done === true)} / {String(productionPromotionDryRun.worker_deep_scan_execution_done === true)} / {String(productionPromotionDryRun.provider_backed_acceptance_done === true)} / {String(productionPromotionDryRun.deepseek_model_ledger_complete === true)}</p>
        <p>browser promoted / durable evidence / legacy retirement: {String(productionPromotionDryRun.browser_visual_performance_promoted === true)} / {String(productionPromotionDryRun.durable_evidence_complete === true)} / {String(productionPromotionDryRun.legacy_retirement_ready === true)}</p>
        <p>worker_started / provider_model_task / production complete: {String(productionPromotionDryRun.worker_started === true)} / {String(productionPromotionDryRun.creates_provider_model_task === true)} / {String(productionPromotionDryRun.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionPromotionDryRun.tushare_called === true)} / {String(productionPromotionDryRun.deepseek_called === true)} / {String(productionPromotionDryRun.github_called === true)}</p>
        <p>这个 dry-run 只把“可以进入提升审查的本地 scope”绑定起来；真实 worker、provider call ledger、DeepSeek model ledger、浏览器 promotion 和 legacy retirement 仍是直接证据缺口。</p>
        <DataLineageTable rows={objectRow(productionPromotionDryRun)} />
        <DataLineageTable rows={productionPromotionDryRunRows} />
        </PacketCard>

        <PacketCard title="雷达 legacy retirement review" subtitle="POST /api/candidate-radar/legacy-retirement-review；审查旧雷达退场边界，不退掉 legacy、不运行外部任务" status={String(legacyRetirementReview.status ?? "missing")}>
        <div className="actions">
          <button
            onClick={launchLegacyRetirementReview}
            disabled={!productionPromotionDryRun.promotion_scope_hash}
            title={productionPromotionDryRun.promotion_scope_hash ? "审查 legacy retirement 边界；不退掉 fallback" : "先生成 production promotion dry-run scope hash"}
            aria-label="create legacy retirement review after promotion dry run scope hash"
          >
            生成 legacy retirement review
          </button>
        </div>
        <p>local_review_ready: {String(legacyRetirementReview.local_review_ready === true)}；ready_to_retire_legacy: {String(legacyRetirementReview.ready_to_retire_legacy === true)}</p>
        <p>legacy_retirement_ready: {String(legacyRetirementReview.legacy_retirement_ready === true)}；legacy_fallback_required: {String(legacyRetirementReview.legacy_fallback_required !== false)}；production_radar_replacement_complete: {String(legacyRetirementReview.production_radar_replacement_complete === true)}</p>
        <p>replacement review / promotion dry-run / durable recipe / stage manifest: {String(legacyRetirementReview.production_replacement_review_ready === true)} / {String(legacyRetirementReview.production_promotion_dry_run_visible === true)} / {String(legacyRetirementReview.durable_evidence_recipe_visible === true)} / {String(legacyRetirementReview.production_stage_manifest_visible === true)}</p>
        <p>worker full/deep / provider / DeepSeek ledger / browser promoted: {String(legacyRetirementReview.worker_full_pool_execution_done === true)} / {String(legacyRetirementReview.worker_deep_scan_execution_done === true)} / {String(legacyRetirementReview.provider_backed_acceptance_done === true)} / {String(legacyRetirementReview.deepseek_model_ledger_complete === true)} / {String(legacyRetirementReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(legacyRetirementReview.local_blocker_count ?? 0)} / {String(legacyRetirementReview.production_blocker_count ?? 0)}；retirement scope: {String(legacyRetirementReview.retirement_scope_hash_short ?? "--")}</p>
        <p>worker_started / provider_model_task / production complete: {String(legacyRetirementReview.worker_started === true)} / {String(legacyRetirementReview.creates_provider_model_task === true)} / {String(legacyRetirementReview.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(legacyRetirementReview.tushare_called === true)} / {String(legacyRetirementReview.deepseek_called === true)} / {String(legacyRetirementReview.github_called === true)}</p>
        <p>这个 review 只把旧雷达何时可以退场讲清楚；真实 worker/provider/model/browser 证据和发布证据没有完成前，legacy/admin/debug fallback 继续保留。</p>
        <DataLineageTable rows={objectRow(legacyRetirementReview)} />
        <DataLineageTable rows={legacyRetirementReviewRows} />
        </PacketCard>

        <PacketCard title="雷达 production promotion review" subtitle="POST /api/candidate-radar/production-promotion-review；审查 promotion 边界，不运行 worker/provider/model/browser" status={String(productionPromotionReview.status ?? "missing")}>
        <div className="actions">
          <button
            onClick={launchProductionPromotionReview}
            disabled={!productionPromotionDryRun.promotion_scope_hash || !legacyRetirementReview.local_review_ready}
            title={productionPromotionDryRun.promotion_scope_hash && legacyRetirementReview.local_review_ready ? "审查 production promotion 边界；不标记 production complete" : "先完成 promotion dry-run scope 和 legacy retirement local review"}
            aria-label="create production promotion review after promotion dry run and legacy retirement review are ready"
          >
            生成 production promotion review
          </button>
        </div>
        <p>local_review_ready: {String(productionPromotionReview.local_review_ready === true)}；ready_to_mark_production: {String(productionPromotionReview.ready_to_mark_production_radar_replacement_complete === true)}</p>
        <p>promotion scope match: {String(productionPromotionReview.requested_promotion_scope_hash_matches_latest === true)}；promotion scope: {String(productionPromotionReview.promotion_scope_hash_short ?? "--")}；review scope: {String(productionPromotionReview.promotion_review_scope_hash_short ?? "--")}</p>
        <p>replacement review / promotion dry-run / legacy review / durable recipe: {String(productionPromotionReview.production_replacement_review_ready === true)} / {String(productionPromotionReview.production_promotion_dry_run_visible === true)} / {String(productionPromotionReview.legacy_retirement_review_visible === true)} / {String(productionPromotionReview.durable_evidence_recipe_visible === true)}</p>
        <p>worker full/deep / provider / DeepSeek ledger / browser promoted: {String(productionPromotionReview.worker_full_pool_execution_done === true)} / {String(productionPromotionReview.worker_deep_scan_execution_done === true)} / {String(productionPromotionReview.provider_backed_acceptance_done === true)} / {String(productionPromotionReview.deepseek_model_ledger_complete === true)} / {String(productionPromotionReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionPromotionReview.local_blocker_count ?? 0)} / {String(productionPromotionReview.production_blocker_count ?? 0)}</p>
        <p>worker_started / provider_model_task / production complete: {String(productionPromotionReview.worker_started === true)} / {String(productionPromotionReview.creates_provider_model_task === true)} / {String(productionPromotionReview.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionPromotionReview.tushare_called === true)} / {String(productionPromotionReview.deepseek_called === true)} / {String(productionPromotionReview.github_called === true)}</p>
        <p>这个 review 只把 LTG-13 promotion 边界写成可审计本地收据；真实 worker/provider/model/browser/release 证据未完成前，不能标记生产替代。</p>
        <DataLineageTable rows={objectRow(productionPromotionReview)} />
        <DataLineageTable rows={productionPromotionReviewRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>耐久证据 / stage manifest 审计</summary>
        <PacketCard title="雷达耐久证据配方" subtitle="candidate_radar_durable_evidence_recipe；生产替代前的直接证据清单，不运行扫描、不外联" status={String(durableEvidenceRecipe.status ?? "missing")}>
          <p>scope: {String(durableEvidenceRecipe.scope ?? "local_candidate_radar_durable_evidence_recipe_no_scan_or_provider_call")}</p>
          <p>local_recipe_ready: {String(durableEvidenceRecipe.local_recipe_ready === true)}；durable_evidence_complete: {String(durableEvidenceRecipe.durable_evidence_complete === true)}；durable_promotion_ready: {String(durableEvidenceRecipe.durable_promotion_ready === true)}</p>
          <p>production_radar_replacement_complete: {String(durableEvidenceRecipe.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(durableEvidenceRecipe.legacy_retirement_ready === true)}；legacy_fallback_required: {String(durableEvidenceRecipe.legacy_fallback_required !== false)}</p>
          <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(durableEvidenceRecipe.full_pool_scan_done === true)} / {String(durableEvidenceRecipe.deep_scan_done === true)} / {String(durableEvidenceRecipe.provider_backed_acceptance_done === true)}</p>
          <p>browser_visual_performance_reviewed: {String(durableEvidenceRecipe.browser_visual_performance_reviewed === true)}；deepseek_model_ledger_complete: {String(durableEvidenceRecipe.deepseek_model_ledger_complete === true)}</p>
          <p>cache_get_external_calls / react_render_external_calls: {String(durableEvidenceRecipe.cache_get_external_calls === true)} / {String(durableEvidenceRecipe.react_render_external_calls === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(durableEvidenceRecipe.tushare_called === true)} / {String(durableEvidenceRecipe.deepseek_called === true)} / {String(durableEvidenceRecipe.github_called === true)}</p>
          <p>missing_durable_evidence: {Array.isArray(durableEvidenceRecipe.missing_durable_evidence) ? durableEvidenceRecipe.missing_durable_evidence.join(" / ") : "--"}</p>
          <p>not_allowed_next_steps: {Array.isArray(durableEvidenceRecipe.not_allowed_next_steps) ? durableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "quick scan as production replacement / provider calls from render / legacy retirement from local recipe"}</p>
          <DataLineageTable rows={objectRow(durableEvidenceRecipe)} />
          <DataLineageTable rows={durableEvidenceRows} />
        </PacketCard>

        <PacketCard title="雷达生产阶段清单" subtitle="candidate_radar_production_stage_scope_manifest；本地 direct evidence / pending manifest，不执行扫描、不外联" status={String(productionStageScopeManifest.status ?? "missing")}>
          <p>scope: {String(productionStageScopeManifest.scope ?? "local_candidate_radar_production_stage_scope_manifest_no_execution")}</p>
          <p>local_manifest_ready: {String(productionStageScopeManifest.local_manifest_ready === true)}；production_radar_replacement_complete: {String(productionStageScopeManifest.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(productionStageScopeManifest.legacy_retirement_ready === true)}</p>
          <p>stage_key_count / direct_evidence_stage_count / pending_stage_count / local_evidence_stage_count: {String(productionStageScopeManifest.stage_key_count ?? 0)} / {String(productionStageScopeManifest.direct_evidence_stage_count ?? 0)} / {String(productionStageScopeManifest.pending_stage_count ?? 0)} / {String(productionStageScopeManifest.local_evidence_stage_count ?? 0)}</p>
          <p>direct_evidence_stage_keys: {Array.isArray(productionStageScopeManifest.direct_evidence_stage_keys) ? productionStageScopeManifest.direct_evidence_stage_keys.join(" / ") : "--"}</p>
          <p>pending_stage_keys: {Array.isArray(productionStageScopeManifest.pending_stage_keys) ? productionStageScopeManifest.pending_stage_keys.join(" / ") : "--"}</p>
          <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(productionStageScopeManifest.full_pool_scan_done === true)} / {String(productionStageScopeManifest.deep_scan_done === true)} / {String(productionStageScopeManifest.provider_backed_acceptance_done === true)}</p>
          <p>worker_backed_execution_done / browser_visual_delta_qa_done / durable_ci_evidence_complete: {String(productionStageScopeManifest.worker_backed_execution_done === true)} / {String(productionStageScopeManifest.browser_visual_delta_qa_done === true)} / {String(productionStageScopeManifest.durable_ci_evidence_complete === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(productionStageScopeManifest.tushare_called === true)} / {String(productionStageScopeManifest.deepseek_called === true)} / {String(productionStageScopeManifest.github_called === true)}</p>
          <p>not_allowed_next_steps: {Array.isArray(productionStageScopeManifest.not_allowed_next_steps) ? productionStageScopeManifest.not_allowed_next_steps.join(" / ") : "treat stage manifest as execution / provider coverage / browser promotion / legacy retirement / buy instruction"}</p>
          <DataLineageTable rows={objectRow(productionStageScopeManifest)} />
          <DataLineageTable rows={productionStageScopeRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details" aria-label="candidate radar result delta audit details">
        <summary>结果变化 / 浏览器差异审计</summary>
        <p className="risk-note">结果变化 diff 和 browser visual delta 属于 P4/P6 审计补证；普通路径继续先看候选优先级说明、候选复核清单和搜票结果，不从这里判断交易动作。</p>
        <PacketCard title="雷达结果变化清晰度" subtitle="result_delta_clarity_contract；有上一版持久化 cache 时执行本地 previous-cache diff，浏览器视觉验收仍需单独跑" status={String(resultDeltaClarity.status ?? "missing")}>
          <p>local_result_delta_clarity_ready: {String(resultDeltaClarity.local_result_delta_clarity_ready ?? false)}</p>
          <p>previous_cache_diff_done: {String(resultDeltaClarity.previous_cache_diff_done ?? false)}</p>
          <p>browser_visual_delta_qa_done: {String(resultDeltaClarity.browser_visual_delta_qa_done ?? false)}</p>
          <p>candidate_delta_signature: {String(resultDeltaClarity.candidate_delta_signature ?? "--")}</p>
          <p>previous_candidate_count: {String(resultDeltaClarity.previous_candidate_count ?? 0)}；added: {String(resultDeltaClarity.candidate_added_count ?? 0)}；removed: {String(resultDeltaClarity.candidate_removed_count ?? 0)}；rank_changed: {String(resultDeltaClarity.candidate_rank_changed_count ?? 0)}</p>
          <p>候选数量、截断、跳过原因、provider gap、freshness、scan mode、上一版 diff 和 full/deep 边界必须可见；浏览器视觉 QA 仍是 pending，不能当生产雷达替代完成。</p>
          <DataLineageTable rows={objectRow(resultDeltaClarity)} />
          <DataLineageTable rows={resultDeltaClarityRows} />
          <DataLineageTable rows={previousCacheDiffRows} />
        </PacketCard>
      </details>

      <PacketCard title="候选优先级说明" subtitle="candidate_priority_explanation_contract；只解释现有缓存排名，不重排、不打新分" status={String(candidatePriorityExplanation.status ?? "missing")}>
        <p>sort_order_source: {String(candidatePriorityExplanation.sort_order_source ?? "existing_candidate_rows_order")}</p>
        <p>explained_candidate_count: {String(candidatePriorityExplanation.explained_candidate_count ?? 0)}；explanation_gap_count: {String(candidatePriorityExplanation.explanation_gap_count ?? 0)}；data_gap_visible_count: {String(candidatePriorityExplanation.data_gap_visible_count ?? 0)}</p>
        <p>uses_existing_rank_only: {String(candidatePriorityExplanation.uses_existing_rank_only === true)}；uses_existing_score_only: {String(candidatePriorityExplanation.uses_existing_score_only === true)}；priority_explanation_is_not_trade_signal: {String(candidatePriorityExplanation.priority_explanation_is_not_trade_signal === true)}</p>
        <p>本面板只说明缓存里的 rank、score、证据摘要、触发/失效条件和 data_gaps；不会重新排序、不会计算 action、不会刷新 provider。</p>
        <DataLineageTable rows={objectRow(candidatePriorityExplanation)} />
        <DataLineageTable rows={candidatePriorityExplanationRows} />
      </PacketCard>

      <details className="developer-audit-details">
        <summary>浏览器 QA 审计</summary>
        <PacketCard title="候选雷达浏览器 QA 手册" subtitle="candidate_browser_qa_runbook_contract；复用本地 runner，不打开浏览器、不写 artifact" status={String(browserQaRunbook.status ?? "missing")}>
          <p>route: {String(browserQaRunbook.candidate_route ?? "#candidates")}</p>
          <p>runner: {String(browserQaRunbook.shared_runner_script ?? "scripts/motion_browser_qa_runner.mjs")}</p>
          <p>visual_qa_complete: {String(browserQaRunbook.visual_qa_complete === true)}</p>
          <p>browser_performance_trace_done: {String(browserQaRunbook.browser_performance_trace_done === true)}</p>
          <p>production_radar_replacement_complete: {String(browserQaRunbook.production_radar_replacement_complete === true)}</p>
          <DataLineageTable rows={objectRow(browserQaRunbook)} />
          <DataLineageTable rows={browserQaRunbookRows} />
          <DataLineageTable rows={browserQaMatrixRows} />
        </PacketCard>

        <PacketCard title="候选雷达浏览器 QA 证据" subtitle="candidate_browser_qa_evidence_summary；只读本地 ignored runner 报告，不打开浏览器、不提交截图" status={String(browserQaEvidence.status ?? "missing")}>
          <div className="actions">
            <button onClick={launchBrowserQaReview}>审查 browser QA 本地证据</button>
          </div>
          <p>local_browser_qa_evidence_found: {String(browserQaEvidence.local_browser_qa_evidence_found === true)}</p>
          <p>candidate_visual_qa_evidence_passed: {String(browserQaEvidence.candidate_visual_qa_evidence_passed === true)}</p>
          <p>candidate_browser_performance_evidence_passed: {String(browserQaEvidence.candidate_browser_performance_evidence_passed === true)}</p>
          <p>motion_viewport_coverage_complete: {String(browserQaEvidence.motion_viewport_coverage_complete === true)}</p>
          <p>default_motion_viewports: {Array.isArray(browserQaEvidence.default_motion_viewports) ? browserQaEvidence.default_motion_viewports.join(" / ") : "--"}</p>
          <p>reduced_motion_viewports: {Array.isArray(browserQaEvidence.reduced_motion_viewports) ? browserQaEvidence.reduced_motion_viewports.join(" / ") : "--"}</p>
          <p>missing_default_motion_viewports / missing_reduced_motion_viewports: {Array.isArray(browserQaEvidence.missing_default_motion_viewports) ? browserQaEvidence.missing_default_motion_viewports.join(" / ") : "--"} / {Array.isArray(browserQaEvidence.missing_reduced_motion_viewports) ? browserQaEvidence.missing_reduced_motion_viewports.join(" / ") : "--"}</p>
          <p>review_required_count: {String(browserQaEvidence.review_required_count ?? 0)}</p>
          <p>latest_report_path: {String(browserQaEvidence.latest_report_path ?? "--")}</p>
          <p>production_radar_replacement_complete: {String(browserQaEvidence.production_radar_replacement_complete === true)}</p>
          <p>legacy_retirement_ready: {String(browserQaEvidence.legacy_retirement_ready === true)}</p>
          <p>该证据只说明本机显式 browser runner 的 `#candidates` 路由结果；不会启动服务、不会打开浏览器、不会调用 provider/model/GitHub，也不能替代 full-pool/deep-scan/provider-backed 验收。</p>
          <DataLineageTable rows={objectRow(browserQaEvidence)} />
          <DataLineageTable rows={browserQaEvidenceRows} />
        </PacketCard>

        <PacketCard title="候选雷达 browser QA 审查" subtitle="candidate_browser_qa_review_contract；POST 按钮门控，只审查本地 ignored artifact" status={String(browserQaReview.status ?? "missing")}>
          <p>explicit_review_task_done: {String(browserQaReview.explicit_review_task_done === true)}</p>
          <p>local_browser_qa_review_ready: {String(browserQaReview.local_browser_qa_review_ready === true)}</p>
          <p>blocking_review_count: {String(browserQaReview.blocking_review_count ?? 0)}</p>
          <p>default_motion_passed: {String(browserQaReview.default_motion_passed === true)}；reduced_motion_passed: {String(browserQaReview.reduced_motion_passed === true)}</p>
          <p>motion_viewport_coverage_complete: {String(browserQaReview.motion_viewport_coverage_complete === true)}</p>
          <p>missing_default_motion_viewports / missing_reduced_motion_viewports: {Array.isArray(browserQaReview.missing_default_motion_viewports) ? browserQaReview.missing_default_motion_viewports.join(" / ") : "--"} / {Array.isArray(browserQaReview.missing_reduced_motion_viewports) ? browserQaReview.missing_reduced_motion_viewports.join(" / ") : "--"}</p>
          <p>production_radar_replacement_complete: {String(browserQaReview.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(browserQaReview.legacy_retirement_ready === true)}</p>
          <p>browser QA review 不运行浏览器、不写 artifact、不提交截图；即使本地审查 ready，也不能解除 full-pool/deep-scan/provider-backed 阻断项。</p>
          <DataLineageTable rows={objectRow(browserQaReview)} />
          <DataLineageTable rows={browserQaReviewRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>Deep-scan 计划 / 本地审查审计</summary>
        <PacketCard title="Deep-scan 准备清单" subtitle="POST /api/candidate-radar/deep-scan-plan；只生成不降能验收单，不执行 deep_scan" status={String(deepScanPlan.status ?? "plan_missing")}>
          <p>deep_scan_plan 是 plan-only：不刷新 provider、不调用 DeepSeek、不执行 deep_scan、不生成买入候选、不修改交易策略。</p>
          <p>feature_loss_gaps_visible: {String(policy.deep_scan_feature_loss_gaps_visible === true)}</p>
          <p>page_render_starts_deep_scan: {String(deepScanPlan.page_render_starts_deep_scan === true)}</p>
          <DataLineageTable rows={objectRow(deepScanPlan)} />
          <DataLineageTable rows={deepScanStageRows} />
          <DataLineageTable rows={deepScanParityRows} />
          <DataLineageTable rows={deepScanSignalRows} />
          <DataLineageTable rows={deepScanBlockerRows} />
        </PacketCard>

        <PacketCard title="Deep-scan 本地审查收据" subtitle="POST /api/candidate-radar/deep-scan-local-review；只审查本地证据和缺口，不调用 DeepSeek" status={String(deepScanLocalReviewReceipt.status ?? "local_review_missing")}>
          <p>local_deep_scan_review_done: {String(deepScanLocalReviewReceipt.local_deep_scan_review_done === true)}；deep_scan_done: {String(deepScanLocalReviewReceipt.deep_scan_done === true)}</p>
          <p>deepseek_called: {String(deepScanLocalReviewReceipt.deepseek_called === true)}；provider_backed_acceptance_done: {String(deepScanLocalReviewReceipt.provider_backed_acceptance_done === true)}</p>
          <p>本地 deep review 只审查候选证据、触发/失效、retained coverage、provider 和 freshness 缺口；不刷新 provider、不调用模型、不生成买入指令。</p>
          <DataLineageTable rows={objectRow(deepScanLocalReviewReceipt)} />
          <DataLineageTable rows={deepScanLocalReviewRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>旧雷达 coverage / 输出合同审计</summary>
        <div className="grid">
          <PacketCard title="旧雷达 coverage inventory" subtitle="legacy_parity_rows；映射、缺口、未来任务必须分清" status={String(legacyParityInventory.status ?? "partial_parity")}>
            <p>quick_scan_is_full_replacement: {String(legacyParityInventory.quick_scan_is_full_replacement === true)}</p>
            <p>slow_paths_are_future_button_tasks: {String(legacyParityInventory.slow_paths_are_future_button_tasks !== false)}</p>
            <DataLineageTable rows={legacyParityRows} />
          </PacketCard>
          <PacketCard title="旧雷达输出合同" subtitle="legacy_output_contract_rows；字段缺失不造假" status="contract">
            <DataLineageTable rows={legacyOutputRows} />
          </PacketCard>
        </div>

        <PacketCard title="旧雷达 coverage 验收收据" subtitle="legacy_parity_acceptance_receipt；把旧雷达能力逐项转成 production replacement 前置条件" status={String(legacyParityAcceptanceReceipt.status ?? "missing")}>
          <p>local_acceptance_receipt_ready: {String(legacyParityAcceptanceReceipt.local_acceptance_receipt_ready === true)}</p>
          <p>production_radar_replacement_complete: {String(legacyParityAcceptanceReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(legacyParityAcceptanceReceipt.legacy_retirement_ready === true)}；legacy_fallback_required: {String(legacyParityAcceptanceReceipt.legacy_fallback_required !== false)}</p>
          <p>parity_item_count: {String(legacyParityAcceptanceReceipt.parity_item_count ?? 0)}；output_contract_field_count: {String(legacyParityAcceptanceReceipt.output_contract_field_count ?? 0)}；production_ready_count: {String(legacyParityAcceptanceReceipt.production_ready_count ?? 0)}；production_blocker_count: {String(legacyParityAcceptanceReceipt.production_blocker_count ?? 0)}</p>
          <p>full_pool_scan_done: {String(legacyParityAcceptanceReceipt.full_pool_scan_done === true)}；deep_scan_done: {String(legacyParityAcceptanceReceipt.deep_scan_done === true)}；provider_backed_acceptance_done: {String(legacyParityAcceptanceReceipt.provider_backed_acceptance_done === true)}</p>
          <p>这个收据把 Top/Watch/Excluded、证据链、评分维度、触发/失效、持仓对比、候选池来源、扫描过滤、超时回退和手动深研逐项转成验收门槛；gap_reported 不能当不降能完成，不能提前退掉 Streamlit fallback。</p>
          <DataLineageTable rows={objectRow(legacyParityAcceptanceReceipt)} />
          <DataLineageTable rows={legacyParityAcceptanceRows} />
          <DataLineageTable rows={rows(legacyParityAcceptanceReceipt.call_ledger)} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>扫描模式状态审计</summary>
        <PacketCard title="扫描模式状态" subtitle="scan_mode_status_rows；当前本地实现 quick/watchlist/custom，full pool 仍是未来任务" status="mode">
          <DataLineageTable rows={scanModeRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>Full-pool 计划 / 本地执行审计</summary>
        <PacketCard title="Full-pool 准备计划" subtitle="POST /api/candidate-radar/full-pool-plan；只生成计划，不扫描全市场" status={String(fullPoolPlan.status ?? "plan_missing")}>
          <p>full_pool_scan_plan 是 plan-only：不刷新 provider、不执行 full_pool_scan、不生成买入候选、不修改交易策略。</p>
          <p>page_render_starts_full_pool: {String(fullPoolPlan.page_render_starts_full_pool === true)}</p>
          <p>worker_task_required: {String(fullPoolPlan.worker_task_required === true)}</p>
          <DataLineageTable rows={objectRow(fullPoolPlan)} />
          <DataLineageTable rows={fullPoolStageRows} />
          <DataLineageTable rows={fullPoolFilterRows} />
          <DataLineageTable rows={fullPoolSignalRows} />
          <DataLineageTable rows={fullPoolBlockerRows} />
        </PacketCard>

        <PacketCard title="Full-pool 本地执行收据" subtitle="POST /api/candidate-radar/full-pool-local-scan；只消费本地 universe，不代表 provider-backed 全市场验收" status={String(fullPoolLocalExecutionReceipt.status ?? "local_execution_missing")}>
          <p>local_full_pool_execution_done: {String(fullPoolLocalExecutionReceipt.local_full_pool_execution_done === true)}；production_full_pool_scan_done: {String(fullPoolLocalExecutionReceipt.production_full_pool_scan_done === true)}</p>
          <p>provider_backed_acceptance_done: {String(fullPoolLocalExecutionReceipt.provider_backed_acceptance_done === true)}；legacy_retirement_ready: {String(fullPoolLocalExecutionReceipt.legacy_retirement_ready === true)}</p>
          <p>本地 full-pool 只证明显式 POST 消费了本地 universe 并写入 packet；不刷新 provider、不打开模型、不生成买入指令。</p>
          <DataLineageTable rows={objectRow(fullPoolLocalExecutionReceipt)} />
          <DataLineageTable rows={fullPoolLocalExecutionRows} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>本地候选池输入审计</summary>
        <PacketCard title="本地候选池审计" subtitle="local_candidate_pool_audit；watchlist/custom 只读本地输入" status={String(localPoolAudit.input_source ?? "cache")}>
          <DataLineageTable rows={objectRow(localPoolAudit)} />
          <DataLineageTable rows={rows(cache.local_candidate_pool_skipped_rows)} />
        </PacketCard>
      </details>

      <details className="developer-audit-details">
        <summary>跳过 / Freshness 审计</summary>
        <div className="grid">
          <PacketCard title="跳过原因" subtitle="skipped_reason_rows；缺失和降级不会被隐藏" status="coverage">
            <DataLineageTable rows={rows(cache.skipped_reason_rows)} />
          </PacketCard>
          <PacketCard title="Freshness 状态" subtitle="freshness_state；未知或陈旧只作为 research-only 缺口展示" status={String(freshnessState.state ?? "unknown")}>
            <DataLineageTable rows={objectRow(freshnessState)} />
          </PacketCard>
        </div>
      </details>

      <PacketCard title="候选复核清单" subtitle="普通入口只显示标的、分数、状态、证据摘要和边界；原始 candidate_rows 下沉到详情" status="cache">
        <DataLineageTable rows={ordinaryCandidateReviewRows} />
        <details className="developer-audit-details">
          <summary>原始 candidate_rows 审计</summary>
          <p>原始候选字段只用于排查 lineage、data_gaps、trigger/invalidation 和旧雷达兼容；普通复核清单不重算、不排序、不生成交易动作。</p>
          <DataLineageTable rows={rows(cache.candidate_rows)} />
        </details>
      </PacketCard>

      <details className="developer-audit-details" aria-label="candidate radar evidence recovery audit details">
        <summary>后续补证路线审计</summary>
        <p className="risk-note">P4 将手动补证步骤默认收起；普通用户先复核候选、排除原因和安全边界，补证路线只在排查缺口时展开。</p>
        <PacketCard title="后续补证路线" subtitle="只展示手动补证步骤；不会调用旧工具或生成交易动作" status="recovery">
          <DataLineageTable rows={rows(cache.evidence_recovery_actions)} />
        </PacketCard>
      </details>

      <div className="grid">
        <PacketCard title="排除候选" subtitle="只读展示被排除的候选；用于复核原因，不做交易判断" status="excluded">
          <DataLineageTable rows={rows(cache.excluded_candidates)} />
        </PacketCard>
      </div>

      <PacketCard title="候选雷达安全边界" subtitle="页面只读展示缓存；扫描必须由按钮触发" status="policy">
        <p>本页不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单，不修改交易策略。</p>
        <p>候选分数只显示本地缓存；不是买入/卖出指令，不进入交易动作，也不改持仓。</p>
        <details className="developer-audit-details">
          <summary>安全边界明细</summary>
          <DataLineageTable rows={[policy]} />
        </details>
      </PacketCard>

      <details className="developer-audit-details">
        <summary>cache payload / lineage 调试审计</summary>
        <div className="grid">
          <PacketCard title="旧工作台桥接" subtitle="只读 old_workspace_packet_bridge" status="bridge">
            <DataLineageTable rows={objectRow(cache.old_workspace_packet_bridge)} />
          </PacketCard>
          <PacketCard title="雷达 packet 摘要" subtitle="脱敏只读 radar_packet" status={String(radarPacket.status ?? "cache")}>
            <DataLineageTable rows={objectRow(radarPacket)} />
          </PacketCard>
        </div>

        <PacketCard title="调用血缘" subtitle="local_candidate_radar_cache；不外联、不写回" status="lineage">
          <DataLineageTable rows={payloadCallLedger} />
        </PacketCard>

        <PacketCard title="GET candidate envelope call_ledger" subtitle="GET /api/candidate-radar/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
          <DataLineageTable rows={cacheCallLedger} />
        </PacketCard>

        <PacketCard title="GET candidate envelope warnings" subtitle="顶层响应提示；不包含敏感凭据或错误堆栈" status="warnings">
          <DataLineageTable rows={warningRows} />
        </PacketCard>

        <PacketCard title="原始 candidate radar cache payload" subtitle="调试用 JSON；不含敏感凭据或错误堆栈" status="safe">
          <JsonDetails title="candidate radar cache raw" data={cache} />
        </PacketCard>
      </details>
    </>
  );
}
