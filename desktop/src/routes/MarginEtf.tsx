import { useEffect, useState } from "react";
import { getBootstrapStatus, getCandidateRadarCache, getPacket, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function text(value: unknown, fallback = "--") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function ordinaryText(value: unknown, fallback = "--") {
  let result = text(value, fallback);
  const replacements: Array<[RegExp, string]> = [
    [/cache_missing/gi, "本地缓存缺口"],
    [/degraded/gi, "待补"],
    [/\bfailed\b/gi, "读取失败"],
    [/\bwaiting\b/gi, "等待"],
    [/\bloading\b/gi, "读取中"],
    [/\bgood\b/gi, "正常"],
    [/\bwarn\b/gi, "待补"],
    [/Tushare/gi, "外部数据"],
    [/DeepSeek/gi, "模型解释"],
    [/GitHub/gi, "远端检查"],
    [/Streamlit/gi, "旧工具"],
    [/fallback/gi, "回退入口"],
    [/data capability/gi, "数据能力"],
    [/research-only/gi, "仅研究"],
    [/\bGET\b/g, "读取"],
    [/\bcache\b/gi, "本地缓存"],
    [/call_ledger/gi, "数据记录"],
    [/ledger/gi, "数据记录"],
    [/packet/gi, "本地快照"],
    [/receipt/gi, "回执"],
    [/scope hash/gi, "范围校验"],
    [/payload/gi, "请求范围"],
    [/envelope/gi, "结果来源"],
    [/review/gi, "复核"],
    [/task_id/gi, "任务编号"],
    [/task=/gi, "任务编号="],
    [/\btask\b/gi, "后台流程"],
    [/\bTask\b/g, "后台流程"]
  ];
  for (const [pattern, replacement] of replacements) {
    result = result.replace(pattern, replacement);
  }
  return result
    .replace(/外部数据\/模型解释\/远端检查/g, "外部数据或模型、远端检查")
    .replace(/本地 本地快照/g, "本地快照")
    .replace(/本地 本地缓存/g, "本地缓存")
    .replace(/只显示 待补\/等待态/g, "只显示待补等待态")
    .replace(/数据记录记录/g, "数据记录");
}

function percent(value: unknown) {
  if (value === undefined || value === null || value === "") return "待验证";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return `${numeric % 1 === 0 ? numeric.toFixed(0) : numeric.toFixed(1)}%`;
  return text(value);
}

function numeric(value: unknown, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

const runtimeModeLabels: Record<string, string> = {
  cache_only: "cache_only（只读缓存，不外联）",
  manual: "manual（仅手动按钮任务）",
  live_light: "live_light（轻量后台口径，页面渲染仍不外联）",
  live_full: "live_full（完整实时模式预留关闭）"
};

function runtimeModeLabel(value: unknown) {
  const mode = text(value, "cache_only");
  return runtimeModeLabels[mode] ?? `未知运行模式：${mode}`;
}

function chainValue(row: Record<string, unknown>, key: string, fallback: unknown = "待验证") {
  const match = rows(row.evidence_chain).find((item) => text(item.key, "") === key || text(item.label, "") === key);
  return text(match?.value ?? fallback, "待验证");
}

function etfLabel(row: Record<string, unknown>) {
  const name = text(row.name || row.etf_name || row.fund_name || row.code || row.etf_code);
  const code = text(row.code || row.etf_code || row.ts_code, "");
  return code ? `${name} (${code})` : name;
}

function etfRows(value: unknown, fallbackSource: string) {
  return rows(value).slice(0, 8).map((row) => ({
    ETF: etfLabel(row),
    状态: text(row.status_label || row.state || row.action_state, "观察"),
    来源: text(row.source, fallbackSource),
    理由: text(row.reason || row.trigger_condition || row.evidence_chain_summary || row.risk_note, "等本地快照补充"),
    流动性: chainValue(row, "liquidity", row.liquidity_text),
    重叠: chainValue(row, "overlap", row.holding_overlap || row.overlap_risk),
    "现金/杠杆": chainValue(row, "margin_cash", row.margin_guardrail || row.cash_buffer),
    边界: text(row.action_guardrail, "不是买入或加融资指令")
  }));
}

function textRows(value: unknown, source: string) {
  const list = Array.isArray(value) ? value : value ? [value] : [];
  return list.slice(0, 8).map((item, index) => ({
    序号: index + 1,
    内容: text(item),
    来源: source,
    边界: "只读提示，不生成交易动作"
  }));
}

const DATA_CAPABILITY_HREF = "#dataCapability";
const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";

export default function MarginEtf() {
  const [etfPacket, setEtfPacket] = useState<Record<string, unknown>>({});
  const [marginPacket, setMarginPacket] = useState<Record<string, unknown>>({});
  const [candidateRadarCache, setCandidateRadarCache] = useState<Record<string, unknown>>({});
  const [candidateRadarCacheError, setCandidateRadarCacheError] = useState("");
  const [callLedger, setCallLedger] = useState<Array<Record<string, unknown>>>([]);
  const [warnings, setWarnings] = useState<Array<string>>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [taskSubmitting, setTaskSubmitting] = useState(false);
  const [taskError, setTaskError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshCandidateRadarCache = () => {
    setCandidateRadarCacheError("");
    void getCandidateRadarCache()
      .then((res) => {
        if (res.ok !== false) {
          setCandidateRadarCache(res.data ?? {});
        } else {
          setCandidateRadarCache({});
          setCandidateRadarCacheError(res.error ?? "candidate_radar_cache_not_ok");
        }
      })
      .catch((err) => {
        setCandidateRadarCache({});
        setCandidateRadarCacheError(err instanceof Error ? err.message : String(err));
      });
  };

  const refresh = () => {
    setLoading(true);
    setError("");
    refreshCandidateRadarCache();
    Promise.all([
      getPacket("command_center_etf_packet"),
      getPacket("command_center_margin_packet")
    ])
      .then(([etfRes, marginRes]) => {
        setEtfPacket(etfRes.data ?? {});
        setMarginPacket(marginRes.data ?? {});
        setCallLedger([...(etfRes.call_ledger ?? []), ...(marginRes.call_ledger ?? [])]);
        setWarnings([...(etfRes.warnings ?? []), ...(marginRes.warnings ?? [])]);
        const firstError = etfRes.ok === false ? etfRes.error : marginRes.ok === false ? marginRes.error : "";
        if (firstError) setError(firstError);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    void getBootstrapStatus().then((res) => {
      if (res.ok !== false) setBootstrapStatus(res.data ?? {});
    });
  }, []);

  const launchLocalRefreshTask = () => {
    const createTask = postTask;
    setTaskSubmitting(true);
    setTaskError("");
    void createTask("/api/market/margin-etf-local-refresh", {
      source: "margin_etf_page_button",
      mode: "local_packet_replay",
      requested_packet_keys: ["command_center_etf_packet", "command_center_margin_packet"],
    })
      .then((res) => {
        setTaskReceipt(res);
        if (res.ok) {
          setTaskId(res.data.task_id);
        } else {
          setTaskError(res.error ?? "margin_etf_local_refresh_task_failed");
        }
      })
      .catch((err) => setTaskError(err instanceof Error ? err.message : String(err)))
      .finally(() => setTaskSubmitting(false));
  };

  const source = text(etfPacket.source, "融资 ETF 本地配置快照");
  const dataStatus = text(etfPacket.data_status ?? etfPacket.cache_state, "missing");
  const recommendedEtfs = rows(etfPacket.recommended_etfs);
  const actionableEtfs = rows(etfPacket.actionable_etfs);
  const watchEtfs = rows(etfPacket.watch_etfs);
  const avoidEtfs = rows(etfPacket.avoid_etfs);
  const excludedEtfs = rows(etfPacket.excluded_etfs);
  const allVisibleEtfRows = [
    ...etfRows(recommendedEtfs.length ? recommendedEtfs : actionableEtfs, source),
    ...etfRows(watchEtfs, source),
    ...etfRows(avoidEtfs, source),
    ...etfRows(excludedEtfs, source)
  ].slice(0, 12);
  const noEtfRows = !allVisibleEtfRows.length;
  const etfPacketLoaded = Object.keys(etfPacket).length > 0;
  const marginPacketLoaded = Object.keys(marginPacket).length > 0;
  const empty = !loading && !error && !etfPacketLoaded && !marginPacketLoaded;
  const marginStatus = text(marginPacket.status ?? marginPacket.capability_state, "waiting");
  const marginSnapshotReady = marginStatus === "ready";
  const ordinaryStatus = loading
    ? "正在读取本地快照"
    : error
      ? "本地快照待补"
      : noEtfRows
        ? "风险快照待补"
        : "本地快照可读";
  const dataStatusLabel = dataStatus === "ready" || dataStatus === "cached"
    ? "本地快照可读"
    : "本地快照待补";
  const marginStatusLabel = marginSnapshotReady ? "融资状态可读" : "融资状态待补";
  const currentMarginRatio = etfPacket.current_margin_ratio ?? marginPacket.current_margin_ratio ?? marginPacket.margin_ratio;
  const recommendedMarginRatio = etfPacket.recommended_margin_ratio;
  const recommendedCashRatio = etfPacket.recommended_cash_ratio;
  const allowNewMargin = etfPacket.allow_new_margin === true;
  const marginDecision = allowNewMargin ? "现金优先，小额也要等触发条件" : "不新增融资";
  const runtimeMode = text(bootstrapStatus.mode, "cache_only");
  const bootstrapPacketReady = bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet";
  const nextStep = noEtfRows
    ? "先读取或手动刷新本地 ETF/融资快照"
    : "先看推荐/观察/回避分组，再复核流动性、重叠和融资现金线";
  const taskDisabledReason = loading
    ? "等待本地快照读取完成后再刷新"
    : error
      ? "本地快照读取异常；先恢复本地服务连接"
      : "";
  const taskDegradedReason = noEtfRows
    ? "当前没有 ETF 候选；刷新只生成本地待补回放，不会自动外联补数据。"
    : "";
  const boundary =
    "页面打开只读本地快照；不会自动全量发现 ETF，不刷新外部数据或模型，不下单，不把 ETF 候选写成买入或加融资指令。";
  const ordinaryQuickReadSummary = noEtfRows
    ? "当前没有可读 ETF 候选：先看本地快照状态和融资现金线，必要时只刷新本地回放。"
    : `当前可读 ${allVisibleEtfRows.length} 行 ETF 候选：先看来源、理由、流动性、重叠和现金/杠杆，再决定是否继续研究。`;
  const ordinaryMissingEvidence = noEtfRows
    ? "缺 ETF 候选行；本地刷新只生成待补回放，不自动补外部数据。"
    : marginSnapshotReady
      ? "继续人工复核重叠、流动性和现金线；候选仍不是买入指令。"
      : "融资状态仍待本地包回放；不要把缺失数据当作可加杠杆。";
  const ordinaryPlainConclusion = noEtfRows
    ? "还没有可读 ETF 候选；先看融资现金线，保持观察，不新增融资。"
    : `当前有 ${allVisibleEtfRows.length} 行 ETF 候选；${marginDecision}，先看流动性、重叠和现金线。`;
  const ordinaryPlainGap = noEtfRows
    ? "缺少 ETF 候选行；本地刷新只会回放已有快照，不会自动补外部数据。"
    : marginSnapshotReady
      ? "仍要人工复核重叠、流动性和现金线；候选不是买入或加融资指令。"
      : "融资状态还没回放完整；不要把缺失当作可加杠杆。";
  const ordinaryPlainNow = noEtfRows
    ? "先看融资现金线；需要更新时点刷新本地回放或重建本地包。"
    : "先看 ETF 候选分组，再看融资现金线和风险提示；换票回下一票雷达。";
  const ordinaryPlainSafety = "ETF 候选只供研究，不是买入、加仓、加融资或下单指令。";
  const candidateRadarReceipt = (candidateRadarCache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarProviderModelAcceptance =
    (candidateRadarCache.search_quant_provider_model_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarSmallDataWriteback =
    (candidateRadarCache.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarInterpretation =
    (candidateRadarCache.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarDeepSeekExplanation =
    (candidateRadarCache.search_quant_deepseek_explanation as Record<string, unknown> | undefined) ?? {};
  const candidateRadarDeepSeekPayload =
    (candidateRadarDeepSeekExplanation.payload as Record<string, unknown> | undefined) ?? {};
  const candidateRadarDeepSeekModelLedger =
    (candidateRadarCache.search_quant_deepseek_model_ledger as Record<string, unknown> | undefined) ?? {};
  const candidateRadarResultLineage =
    (candidateRadarCache.search_quant_current_result_lineage as Record<string, unknown> | undefined) ??
    (candidateRadarCache.search_quant_result_lineage as Record<string, unknown> | undefined) ??
    (candidateRadarProviderModelAcceptance.result_lineage as Record<string, unknown> | undefined) ??
    {};
  const candidateRadarResultVersionSummary =
    (candidateRadarCache.search_quant_result_version_summary as Record<string, unknown> | undefined) ??
    (candidateRadarProviderModelAcceptance.result_version_summary as Record<string, unknown> | undefined) ??
    {};
  const candidateRadarResultVersion = text(
    candidateRadarResultVersionSummary.current_result_version ??
      candidateRadarResultVersionSummary.latest_task_result_version ??
      candidateRadarResultLineage.result_version,
    ""
  );
  const candidateRadarSourceTaskId = text(
    candidateRadarResultVersionSummary.current_result_task_id ??
      candidateRadarResultVersionSummary.latest_task_id ??
      candidateRadarResultLineage.task_id ??
      candidateRadarProviderModelAcceptance.task_id ??
      candidateRadarReceipt.latest_task_id,
    ""
  );
  const candidateRadarResultLedgerIds = Array.isArray(candidateRadarResultLineage.provider_call_ledger_ids)
    ? candidateRadarResultLineage.provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
    : Array.isArray(candidateRadarResultVersionSummary.current_result_provider_call_ledger_ids)
      ? candidateRadarResultVersionSummary.current_result_provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
      : Array.isArray(candidateRadarResultVersionSummary.latest_task_provider_call_ledger_ids)
        ? candidateRadarResultVersionSummary.latest_task_provider_call_ledger_ids.map((item) => String(item)).filter(Boolean)
        : [];
  const candidateRadarProviderLedgerRows = rows(candidateRadarCache.call_ledger).filter((row) => {
    const api = text(row.api, "").toLowerCase();
    const provider = text(row.provider ?? row.source, "").toLowerCase();
    return row.tushare_called === true || provider.includes("tushare") || ["trade_cal", "daily", "daily_basic", "moneyflow"].includes(api);
  });
  const candidateRadarConfirmedSymbol = text(
    candidateRadarCache.latest_confirmed_symbol ??
      candidateRadarCache.search_quant_projection_latest_confirmed_symbol ??
      candidateRadarProviderModelAcceptance.symbol ??
      candidateRadarReceipt.symbol ??
      candidateRadarSmallDataWriteback.symbol ??
      candidateRadarInterpretation.symbol,
    ""
  );
  const candidateRadarProviderSuccessCount = numeric(
    candidateRadarProviderModelAcceptance.provider_api_success_count ??
      candidateRadarReceipt.p1_provider_api_success_count ??
      candidateRadarSmallDataWriteback.provider_api_success_count,
    0
  );
  const candidateRadarProviderCallCount = numeric(
    candidateRadarProviderModelAcceptance.provider_api_call_count ??
      candidateRadarReceipt.p1_provider_api_call_count ??
      candidateRadarSmallDataWriteback.provider_api_call_count,
    candidateRadarProviderSuccessCount
  );
  const candidateRadarProviderTotalCount = candidateRadarProviderCallCount > 0
    ? candidateRadarProviderCallCount
    : candidateRadarProviderSuccessCount;
  const candidateRadarProviderLedgerReady =
    candidateRadarProviderModelAcceptance.tushare_call_ledger_evidence_done === true ||
    candidateRadarReceipt.p1_tushare_first_provider_ledger_ready === true ||
    candidateRadarSmallDataWriteback.source_task_tushare_provider_ledger_ready === true ||
    candidateRadarSmallDataWriteback.provider_call_ledger_replayed_from_source_task === true ||
    candidateRadarSmallDataWriteback.provider_call_ledger_written === true ||
    candidateRadarSmallDataWriteback.ledger_ready === true ||
    candidateRadarProviderSuccessCount > 0;
  const candidateRadarProviderCountLabel = candidateRadarProviderLedgerReady
    ? `Tushare ${candidateRadarProviderSuccessCount}/${candidateRadarProviderTotalCount || candidateRadarProviderSuccessCount} 个接口`
    : "等待确认按钮后的 Tushare-first 数据链";
  const candidateRadarDataDate = text(
    candidateRadarProviderModelAcceptance.data_date ??
      candidateRadarProviderModelAcceptance.trade_date ??
      candidateRadarSmallDataWriteback.data_date ??
      candidateRadarInterpretation.data_date ??
      candidateRadarProviderLedgerRows.find((row) => row.data_date)?.data_date ??
      candidateRadarProviderLedgerRows.find((row) => row.trade_date)?.trade_date ??
      candidateRadarProviderLedgerRows.find((row) => row.end_date)?.end_date,
    "待确认"
  );
  const candidateRadarDataSource = candidateRadarProviderLedgerReady ? "Tushare" : "等待后台确认任务";
  const candidateRadarLineageLabel = candidateRadarResultVersion
    ? `结果版本=${candidateRadarResultVersion}${candidateRadarSourceTaskId ? ` / task=${candidateRadarSourceTaskId}` : ""}`
    : "等待同一 task/result_version";
  const candidateRadarLedgerLineageLabel = candidateRadarResultLedgerIds.length
    ? `${candidateRadarResultLedgerIds.length} 条 provider ledger：${candidateRadarResultLedgerIds.slice(0, 4).join(" / ")}${candidateRadarResultLedgerIds.length > 4 ? " / ..." : ""}`
    : candidateRadarProviderLedgerReady
      ? "provider ledger 可回放；等待 result lineage ids"
      : "等待 provider ledger";
  const candidateRadarDeepSeekLedgerRecorded =
    candidateRadarDeepSeekModelLedger.model_ledger_recorded === true ||
    candidateRadarProviderModelAcceptance.deepseek_model_ledger_recorded === true ||
    candidateRadarProviderModelAcceptance.deepseek_model_ledger_evidence_done === true ||
    Boolean(candidateRadarDeepSeekModelLedger.input_summary_hash || candidateRadarDeepSeekModelLedger.input_hash);
  const candidateRadarDeepSeekExplanationReady =
    candidateRadarDeepSeekExplanation.status === "success" ||
    candidateRadarProviderModelAcceptance.deepseek_output_acceptance_done === true;
  const candidateRadarDeepSeekSafeDegraded =
    candidateRadarProviderModelAcceptance.deepseek_safe_degraded === true ||
    String(candidateRadarDeepSeekExplanation.status ?? "").startsWith("degraded") ||
    String(candidateRadarDeepSeekModelLedger.status ?? "").startsWith("degraded");
  const candidateRadarDeepSeekSkipped =
    candidateRadarProviderModelAcceptance.deepseek_skipped_by_request === true ||
    candidateRadarReceipt.p1_deepseek_skipped_by_request === true ||
    candidateRadarSmallDataWriteback.deepseek_skipped_by_request === true;
  const candidateRadarDeepSeekState = candidateRadarDeepSeekExplanationReady
    ? `DeepSeek 解释已写入安全模型账本：${text(candidateRadarDeepSeekPayload.summary, "只解释来源和缺口，不改数值或动作")}`
    : candidateRadarDeepSeekSafeDegraded
      ? `DeepSeek 已安全降级：${text(candidateRadarProviderModelAcceptance.deepseek_safe_failure_mode ?? candidateRadarDeepSeekModelLedger.safe_failure_mode, "Tushare 数据、Factor light、Candidate Radar、Next Session 继续显示")}`
      : candidateRadarDeepSeekLedgerRecorded
        ? "DeepSeek 安全模型账本已记录；只读 hash、耗时、token/cost 摘要和安全状态"
        : candidateRadarDeepSeekSkipped
          ? "DeepSeek 未请求；Tushare 数据链和风险预算不被阻塞"
          : "DeepSeek 待治理或待确认；不影响 ETF/融资只读风险预算";
  const marginEtfConfirmedDataBridgeSentence = candidateRadarConfirmedSymbol
    ? `当前确认标的 ${candidateRadarConfirmedSymbol} 已从下一票雷达带入风险预算；来源=${candidateRadarDataSource}，数据日期=${candidateRadarDataDate}，${candidateRadarProviderCountLabel}；${candidateRadarLineageLabel}。`
    : candidateRadarCacheError
      ? `下一票雷达缓存暂不可读：${ordinaryText(candidateRadarCacheError)}；ETF/融资仍按本地风险快照显示。`
      : "还没有确认标的带入 ETF/融资；先回下一票雷达输入股票并点击确认。";
  const marginEtfConfirmedDataBridgeItems: MetricItem[] = [
    {
      label: "当前确认标的",
      value: candidateRadarConfirmedSymbol || "等待下一票雷达确认输入",
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "数据来源",
      value: `来源=${candidateRadarDataSource} / 数据日期=${candidateRadarDataDate}`,
      tone: candidateRadarProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "Tushare 数据链",
      value: candidateRadarProviderLedgerReady
        ? `${candidateRadarProviderCountLabel} 已从 POST task 的 cache / call_ledger / packet 回放`
        : candidateRadarCacheError
          ? `候选雷达缓存待补：${ordinaryText(candidateRadarCacheError)}`
          : "等待用户在下一票雷达点击确认按钮后回放",
      tone: candidateRadarProviderLedgerReady ? "good" : "warn"
    },
    {
      label: "结果版本",
      value: candidateRadarLineageLabel,
      tone: candidateRadarResultVersion ? "good" : "warn"
    },
    {
      label: "同源账本",
      value: candidateRadarLedgerLineageLabel,
      tone: candidateRadarResultLedgerIds.length ? "good" : "warn"
    },
    {
      label: "DeepSeek 解释",
      value: candidateRadarDeepSeekState,
      tone: candidateRadarDeepSeekExplanationReady || candidateRadarDeepSeekLedgerRecorded || candidateRadarDeepSeekSkipped ? "good" : "warn"
    },
    {
      label: "ETF/融资承接",
      value: "只把确认结果当风险预算上下文；不覆盖 ETF 候选、现金线、价格、因子或交易动作",
      tone: "good"
    },
    {
      label: "读取边界",
      value: "只读 CandidateRadar cache / call_ledger / packet；不会创建 ETF/融资刷新、不会调用 Tushare/DeepSeek、不会加融资",
      tone: "good"
    }
  ];
  const ordinaryPlainItems: MetricItem[] = [
    {
      label: "一句话",
      value: ordinaryPlainConclusion
    },
    {
      label: "缺口",
      value: ordinaryPlainGap
    },
    {
      label: "现在做什么",
      value: ordinaryPlainNow
    },
    {
      label: "安全说明",
      value: ordinaryPlainSafety
    }
  ];
  const ordinaryQuickReadItems: MetricItem[] = [
    {
      label: "现在能看",
      value: noEtfRows
        ? "暂无 ETF 候选；先看本地快照和融资现金线"
        : `ETF 候选 ${allVisibleEtfRows.length} 行：推荐 ${recommendedEtfs.length} / 观察 ${watchEtfs.length} / 回避 ${avoidEtfs.length} / 排除 ${excludedEtfs.length}`,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "数据来源",
      value: source,
      tone: dataStatus === "ready" || dataStatus === "cached" ? "good" : "warn"
    },
    {
      label: "融资动作",
      value: marginDecision,
      tone: allowNewMargin ? "warn" : "good"
    },
    {
      label: "先看哪儿",
      value: noEtfRows ? "融资现金线 / 风险提示 / 本地回放按钮" : "ETF 候选分组 / 融资现金线 / 风险提示",
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "缺什么",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "不要做",
      value: "不要把 ETF 候选当买入、加仓或加融资指令",
      tone: "good"
    }
  ];
  const marginEtfAppVisibleNowSentence = noEtfRows
    ? "打开 app 能看到 ETF/融资的待补风险快照：先看本地快照、融资现金线和刷新本地回放入口，不新增融资。"
    : `打开 app 能看到 ${allVisibleEtfRows.length} 行 ETF 候选、融资现金线和风险提示；${marginDecision}。`;
  const marginEtfAppVisibleNowItems: MetricItem[] = [
    {
      label: "打开可见",
      value: marginEtfAppVisibleNowSentence
    },
    {
      label: "当前确认标的",
      value: candidateRadarConfirmedSymbol
        ? `${candidateRadarConfirmedSymbol} / 来源=${candidateRadarDataSource} / 数据日期=${candidateRadarDataDate}`
        : "等待下一票雷达确认输入"
    },
    {
      label: "确认后数据链",
      value: candidateRadarProviderLedgerReady
        ? `${candidateRadarProviderCountLabel} 已回放到 cache / call_ledger / packet`
        : "等待确认按钮后的 Tushare-first 结果或明确降级原因"
    },
    {
      label: "DeepSeek 解释状态",
      value: candidateRadarDeepSeekState
    },
    {
      label: "ETF 候选",
      value: noEtfRows
        ? "暂无候选；显示待补/等待状态"
        : `推荐 ${recommendedEtfs.length} / 观察 ${watchEtfs.length} / 回避 ${avoidEtfs.length} / 排除 ${excludedEtfs.length}`
    },
    {
      label: "融资现金线",
      value: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`
    },
    {
      label: "来源层",
      value: `${source} / 本地融资快照 / ${dataStatusLabel}`
    },
    {
      label: "数据能力",
      value: "ETF/融资缺口去数据能力页复核真实数据、权限、空窗口和本地结果状态"
    },
    {
      label: "缺口原因",
      value: noEtfRows ? `${ordinaryMissingEvidence}；先按待补风险快照处理` : "候选已进入本地回放；仍需人工复核流动性、重叠和现金线"
    },
    {
      label: "下一步入口",
      value: noEtfRows ? "刷新本地回放或回下一票雷达换标的" : "先看候选分组，再看风险护栏和下一票雷达"
    },
    {
      label: "安全边界",
      value: "页面打开和本地链接只读；不启动刷新流程、不刷新外部数据或模型、不交易、不加融资、不改写策略"
    }
  ];
  const marginEtfFirstViewportActionSentence = noEtfRows
    ? "首屏下一步：先看融资现金线；需要更新时跳到本地回放按钮；换标的回下一票雷达。"
    : `首屏下一步：先看 ${allVisibleEtfRows.length} 行 ETF 候选，再核对融资现金线；需要更新时跳到本地回放按钮。`;
  const marginEtfFirstViewportActionItems: MetricItem[] = [
    {
      label: "先点哪里",
      value: noEtfRows ? "融资现金线 / 本地回放按钮 / 下一票雷达" : "ETF 候选 / 融资现金线 / 本地回放按钮"
    },
    {
      label: "看 ETF",
      value: noEtfRows ? "暂无候选；先保持观察" : `候选 ${allVisibleEtfRows.length} 行，先按状态和理由复核`
    },
    {
      label: "看现金线",
      value: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 缓冲 ${percent(recommendedCashRatio)}`
    },
    {
      label: "刷新方式",
      value: "首屏链接只定位本地按钮；真正刷新仍要用户点击，不自动补外部数据"
    },
    {
      label: "边界",
      value: "不买入、不加仓、不加融资、不下单"
    }
  ];
  const marginEtfFirstViewportRiskSentence = noEtfRows
    ? "首屏风险卡：暂无 ETF 候选，先看融资现金线和缺口；缺数据按保守处理，不新增融资。"
    : `首屏风险卡：${allVisibleEtfRows.length} 行 ETF 候选只做风险预算参考；${marginDecision}，先核对现金线。`;
  const marginEtfFirstViewportRiskItems: MetricItem[] = [
    {
      label: "候选/现金线",
      value: noEtfRows
        ? `ETF 候选暂无；融资现金线 当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 缓冲 ${percent(recommendedCashRatio)}`
        : `ETF 候选 ${allVisibleEtfRows.length} 行；融资现金线 当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 缓冲 ${percent(recommendedCashRatio)}`,
      tone: noEtfRows || !recommendedCashRatio ? "warn" : "good"
    },
    {
      label: "缺口读法",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "禁令",
      value: "ETF 候选不是买入指令；融资比例不是加杠杆许可",
      tone: "good"
    }
  ];
  const marginEtfPostResearchRiskPathSentence = noEtfRows
    ? "从量化推演或次日图谱过来后，ETF/融资先显示待补风险预算：没有 ETF 候选时保持观察，不新增融资。"
    : `从量化推演或次日图谱过来后，先把 ${allVisibleEtfRows.length} 行 ETF 候选、融资现金线和缺口合成风险预算；${marginDecision}。`;
  const marginEtfPostResearchRiskPathItems: MetricItem[] = [
    {
      label: "来自结果",
      value: "Factor / Next 只给研究结果；ETF/融资只补风险预算，不改结论动作",
      tone: "good"
    },
    {
      label: "先看 ETF",
      value: noEtfRows ? "暂无 ETF 候选；保持观察" : `候选 ${allVisibleEtfRows.length} 行，先看推荐/观察/回避/排除`,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "再看现金线",
      value: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      tone: recommendedCashRatio ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "回流入口",
      value: "数据能力 / 下一票雷达 / 风险护栏 / 今日作战台",
      tone: "good"
    },
    {
      label: "边界",
      value: "不把量化结果、ETF 强弱或融资比例变成买入、加仓、加融资或下单指令",
      tone: "good"
    }
  ];
  const marginEtfPostResearchRiskPathRows = [
    {
      步骤: "1. 从结果页过来",
      当前状态: "Factor / Next 是研究回放入口",
      用户下一步: "只把上游结果当背景，再看 ETF/融资风险预算。",
      入口: "#factor / #next",
      边界: "结果页链接只切换本地页面；不刷新外部数据或模型。"
    },
    {
      步骤: "2. 看 ETF 候选",
      当前状态: noEtfRows ? "暂无可读 ETF 候选" : `${allVisibleEtfRows.length} 行 ETF 候选可读`,
      用户下一步: noEtfRows ? "保持观察，先看融资现金线。" : "按推荐、观察、回避和排除分组复核。",
      入口: "#marginEtf",
      边界: "ETF 候选只做风险预算参考，不是买入或加仓指令。"
    },
    {
      步骤: "3. 看融资现金线",
      当前状态: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      用户下一步: "现金缓冲不足或数据缺失时按保守处理。",
      入口: "#marginEtf",
      边界: "融资比例不是加杠杆许可。"
    },
    {
      步骤: "4. 处理缺口",
      当前状态: ordinaryMissingEvidence,
      用户下一步: "去数据能力页看真实数据、权限、空窗口和本地结果状态。",
      入口: "DATA_CAPABILITY_HREF",
      边界: "缺口只提示补证；不会从本卡启动刷新流程或调用外部数据。"
    },
    {
      步骤: "5. 回到主路径",
      当前状态: "需要换票回下一票雷达；看全局风险回风险护栏。",
      用户下一步: "继续只读复核，不下单、不加融资。",
      入口: "#candidates / #risk / #home",
      边界: "本地链接不启动刷新流程、不交易、不改交易策略。"
    }
  ];
  const marginEtfRiskCardStatus = noEtfRows
    ? "等待 ETF 候选：先看融资现金线，不新增融资。"
    : allowNewMargin
      ? "有 ETF 候选，但融资只允许现金优先、小额待条件。"
      : "有 ETF 候选，但当前结论仍是不新增融资。";
  const marginEtfRiskCardItems: MetricItem[] = [
    {
      label: "ETF 候选",
      value: noEtfRows
        ? "暂无可读候选；只显示等待/待补"
        : `${allVisibleEtfRows.length} 行候选：推荐 ${recommendedEtfs.length} / 观察 ${watchEtfs.length} / 回避 ${avoidEtfs.length} / 排除 ${excludedEtfs.length}`,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "融资现金线",
      value: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      tone: recommendedCashRatio ? "good" : "warn"
    },
    {
      label: "风险口径",
      value: marginDecision,
      tone: allowNewMargin ? "warn" : "good"
    },
    {
      label: "缺口",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "下一步",
      value: noEtfRows
        ? "先看融资现金线；必要时只刷新本地回放。"
        : "先看候选分组，再看融资现金线；换标的回下一票雷达。",
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "禁令",
      value: "不把 ETF 候选当买入、加仓、加融资或下单指令",
      tone: "good"
    }
  ];
  const marginEtfCandidateBridgeSentence = noEtfRows
    ? "从下一票雷达跳过来后，先看融资现金线和缺口：当前没有 ETF 候选，不新增融资，也不把缺数据当低风险。"
    : `从下一票雷达跳过来后，先把 ${allVisibleEtfRows.length} 行 ETF 候选当风险预算参考，再看现金线、重叠和流动性；${marginDecision}。`;
  const marginEtfCandidateBridgeItems: MetricItem[] = [
    {
      label: "候选承接",
      value: noEtfRows ? "暂无 ETF 候选；回下一票雷达换标的或等待本地快照" : `${allVisibleEtfRows.length} 行 ETF 候选可作风险预算参考`,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "先看风险",
      value: "融资现金线、同类重叠、流动性和缺口",
      tone: "good"
    },
    {
      label: "融资口径",
      value: marginDecision,
      tone: allowNewMargin ? "warn" : "good"
    },
    {
      label: "缺口处理",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "回到候选",
      value: "需要换标的或解释单票时回下一票雷达",
      tone: "good"
    },
    {
      label: "安全边界",
      value: "本卡只做风险预算承接；不是买入、加仓、加融资或下单指令",
      tone: "good"
    }
  ];
  const marginEtfCandidateBridgeRows = [
    {
      步骤: "1. 从候选页过来",
      用户看法: "先把候选当研究对象，不当操作建议",
      入口: "#candidates",
      边界: "候选不是买入指令"
    },
    {
      步骤: "2. 看 ETF 替代风险",
      用户看法: noEtfRows ? "没有 ETF 候选时先保持观察" : "先看推荐、观察、回避和排除分组",
      入口: "#marginEtf",
      边界: "ETF 候选只做风险预算参考"
    },
    {
      步骤: "3. 看融资现金线",
      用户看法: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      入口: "#risk",
      边界: "融资比例不是加杠杆许可"
    },
    {
      步骤: "4. 回流",
      用户看法: "换票回下一票雷达；看全局风险回风险护栏",
      入口: "#candidates / #risk",
      边界: "链接只切换本地页面，不启动刷新流程、不交易、不改策略"
    }
  ];
  const marginEtfCashLineSentence = allowNewMargin
    ? "融资现金线显示仍要现金优先；即便允许小额，也必须等触发条件和数据证据齐备。"
    : "融资现金线当前结论是不新增融资；ETF 强弱只能作为研究参考，不能当加杠杆许可。";
  const marginEtfCashLineItems: MetricItem[] = [
    {
      label: "当前融资",
      value: percent(currentMarginRatio)
    },
    {
      label: "建议融资",
      value: percent(recommendedMarginRatio)
    },
    {
      label: "现金缓冲",
      value: percent(recommendedCashRatio)
    },
    {
      label: "读法",
      value: marginEtfCashLineSentence
    },
    {
      label: "缺口",
      value: ordinaryMissingEvidence
    },
    {
      label: "禁令",
      value: "融资比例不是加杠杆许可；ETF 候选不是买入或加融资指令"
    }
  ];
  const marginEtfCashLineRows = [
    {
      读法: "1. 当前融资",
      当前状态: percent(currentMarginRatio),
      用户下一步: "先确认当前融资压力，再看是否需要降低风险敞口。",
      边界: "当前比例只读本地快照，不生成调仓或融资动作。"
    },
    {
      读法: "2. 建议融资",
      当前状态: percent(recommendedMarginRatio),
      用户下一步: allowNewMargin ? "即便允许小额，也要等触发条件和人工复核。" : "保持不新增融资。",
      边界: "建议比例不是下单、加仓或加融资指令。"
    },
    {
      读法: "3. 现金缓冲",
      当前状态: percent(recommendedCashRatio),
      用户下一步: "现金缓冲不足或缺失时按保守处理。",
      边界: "缺数据不等于低风险，也不自动补调外部数据。"
    },
    {
      读法: "4. 回流复核",
      当前状态: ordinaryMissingEvidence,
      用户下一步: "数据缺口去数据能力页；换标的回下一票雷达；全局风险回风险护栏。",
      边界: "本地链接只切换页面，不启动刷新流程、不刷新外部数据或模型、不交易。"
    }
  ];
  const marginEtfRiskCardRows = [
    {
      复核项: "1. ETF 候选",
      当前状态: noEtfRows ? "暂无候选，等待本地快照或待补回放" : `${allVisibleEtfRows.length} 行候选可读`,
      用户下一步: noEtfRows ? "不要主动加风险；先看融资现金线。" : "按推荐、观察、回避、排除分组复核。",
      边界: "候选只表示研究优先级，不是买入、加仓或加融资指令。"
    },
    {
      复核项: "2. 融资现金线",
      当前状态: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      用户下一步: "先确认现金缓冲是否足够，再决定是否继续研究 ETF。",
      边界: "融资比例不是加杠杆许可；缺数据时按保守处理。"
    },
    {
      复核项: "3. 缺口",
      当前状态: ordinaryMissingEvidence,
      用户下一步: noEtfRows ? "只刷新本地回放或回上游补证。" : "继续人工复核重叠、流动性和现金线。",
      边界: "缺口只提示补证，不自动调用外部数据或模型。"
    },
    {
      复核项: "4. 回流",
      当前状态: "可回今日作战台、下一票雷达或风险护栏继续看",
      用户下一步: "换标的回下一票雷达；看整体风险回风险护栏。",
      边界: "本地链接只切换页面，不启动刷新流程、不交易、不改策略。"
    }
  ];
  const localRefreshTask = taskReceipt?.data?.task;
  const localRefreshPayload = localRefreshTask?.payload_safe ?? {};
  const localRefreshLedger = taskReceipt?.call_ledger?.length ? taskReceipt.call_ledger : localRefreshTask?.call_ledger ?? [];
  const localRefreshFirstLedger = localRefreshLedger[0] ?? {};
  const localRefreshDegradedReason = text(
    localRefreshPayload.degraded_reason || localRefreshFirstLedger.failure_mode,
    ""
  );
  const localRefreshRowCount = text(
    localRefreshPayload.etf_row_count ?? localRefreshFirstLedger.row_count ?? allVisibleEtfRows.length,
    "0"
  );
  const localRefreshScopeShort = text(
    localRefreshPayload.scope_hash_short ?? localRefreshFirstLedger.scope_hash_short,
    taskReceipt ? "已生成" : "点击后生成"
  );
  const localRefreshStatus = taskReceipt
    ? taskReceipt.ok
      ? text(localRefreshTask?.current_step ?? localRefreshFirstLedger.call_status, "本地回放已返回")
      : text(taskReceipt.error, "创建失败")
    : taskSubmitting
      ? "正在创建本地回放"
      : "等待点击刷新/重建本地包";
  const localRefreshReadableSummary = taskReceipt
    ? localRefreshDegradedReason
      ? `本地刷新已返回待补结果：${localRefreshDegradedReason}；不会自动补外部数据。`
      : `本地刷新已返回：${localRefreshRowCount} 行 ETF 候选参与回放；继续看候选分组和融资现金线。`
    : taskError
      ? `本地刷新失败：${taskError}`
      : "点击刷新/重建本地包后，这里会显示回执、待补原因、行数和安全说明。";
  const localRefreshResultItems: MetricItem[] = [
    {
      label: "本地回执",
      value: taskReceipt ? text(taskReceipt.data?.task_id, "创建失败") : taskSubmitting ? "正在创建" : "点击后显示",
      tone: taskReceipt?.ok ? "good" : taskError ? "warn" : "neutral"
    },
    {
      label: "本地结果",
      value: localRefreshStatus,
      tone: taskReceipt?.ok ? "good" : taskError ? "warn" : "neutral"
    },
    {
      label: "待补原因",
      value: localRefreshDegradedReason || (taskReceipt ? "未标记待补" : "点击后显示"),
      tone: localRefreshDegradedReason ? "warn" : taskReceipt ? "good" : "neutral"
    },
    {
      label: "ETF 行数",
      value: localRefreshRowCount,
      tone: Number(localRefreshRowCount) > 0 ? "good" : "warn"
    },
    {
      label: "范围校验",
      value: localRefreshScopeShort,
      tone: taskReceipt ? "good" : "neutral"
    },
    {
      label: "安全说明",
      value: "只读本地快照；不补外部数据、不调用模型、不交易",
      tone: "good"
    }
  ];
  const summaryItems: MetricItem[] = [
    { label: "本地快照", value: dataStatus, tone: dataStatus === "ready" || dataStatus === "cached" ? "good" : "warn" },
    { label: "ETF 数量", value: recommendedEtfs.length ? `推荐 ${recommendedEtfs.length}` : "等待快照", tone: recommendedEtfs.length ? "good" : "warn" },
    { label: "当前融资", value: percent(currentMarginRatio), tone: currentMarginRatio ? "warn" : "neutral" },
    { label: "建议融资", value: percent(recommendedMarginRatio), tone: allowNewMargin ? "warn" : "good" },
    { label: "现金缓冲", value: percent(recommendedCashRatio), tone: recommendedCashRatio ? "good" : "warn" },
    { label: "今天动作", value: marginDecision, tone: allowNewMargin ? "warn" : "good" },
    { label: "下一步", value: nextStep },
    { label: "边界", value: "只读研究，不交易", tone: "good" }
  ];
  const modeLayerItems: MetricItem[] = [
    {
      label: "本地读取层",
      value: `本地快照和运行状态只读；运行状态 ${bootstrapPacketReady ? "可读" : "等待回放"}；页面打开、React render 和本地链接不启动刷新流程`,
      tone: bootstrapPacketReady ? "good" : "warn"
    },
    {
      label: "按钮刷新层",
      value: `${runtimeModeLabel(runtimeMode)}；刷新/重建本地包只走用户点击后的本地流程，不刷新外部数据或模型`,
      tone: runtimeMode === "cache_only" ? "good" : "warn"
    },
    {
      label: "数据证据层",
      value: `${dataStatusLabel} / ${marginStatusLabel}；缺 ETF 或融资数据只显示待补风险快照，不当作无风险，也不自动补外部数据`,
      tone: dataStatus === "ready" || dataStatus === "cached" ? "good" : "warn"
    },
    {
      label: "旧入口退场层",
      value: "本页是 ETF/融资普通替代纵切；不打开 Streamlit，不移除 fallback，不把本地回放当 LTG-10 strict closeout",
      tone: "warn"
    },
    {
      label: "交易隔离层",
      value: "ETF 候选和融资比例只供研究复核；不接券商、不下单、不改交易策略",
      tone: "good"
    }
  ];
  const riskRows = [
    ...textRows(etfPacket.risk_notes, "risk_notes"),
    ...textRows(etfPacket.watch_not_chase, "watch_not_chase"),
    ...textRows(etfPacket.margin_risk_notice, "margin_risk_notice"),
    ...textRows(etfPacket.decision_guardrail, "decision_guardrail")
  ].slice(0, 12);
  const marginEtfCandidateReadingSummary = noEtfRows
    ? "暂无 ETF 候选行；先看融资现金线和缺口，不把缺数据当成低风险。"
    : `当前 ${allVisibleEtfRows.length} 行 ETF 候选先按状态和理由阅读，再核对流动性、重叠和现金/杠杆。`;
  const marginEtfCandidateReadingItems: MetricItem[] = [
    {
      label: "逐行读法",
      value: noEtfRows ? "没有候选行时先保持观察" : "先看状态和理由，再看三项风险核对"
    },
    {
      label: "状态含义",
      value: "推荐=优先复核；观察=等触发；回避/排除=不要追高"
    },
    {
      label: "风险核对",
      value: "流动性、同类重叠、现金/杠杆必须一起看"
    },
    {
      label: "缺口处理",
      value: noEtfRows ? ordinaryMissingEvidence : "缺字段按保守处理，不自动补调外部数据"
    },
    {
      label: "边界",
      value: "ETF 行只是风险预算参考，不是买入、加仓、加融资或下单指令"
    }
  ];
  const marginEtfCandidateReadingRows = allVisibleEtfRows.length
    ? allVisibleEtfRows.map((row, index) => ({
        顺序: index + 1,
        ETF: text(row.ETF),
        怎么看: `${text(row.状态, "观察")}：${text(row.理由, "等本地快照补充")}`,
        来源: text(row.来源, source),
        风险核对: `流动性 ${text(row.流动性)} / 重叠 ${text(row.重叠)} / 现金杠杆 ${text(row["现金/杠杆"])}`,
        边界: text(row.边界, "不是买入、加仓或加融资指令")
      }))
    : [
        {
          顺序: "等待",
          ETF: "暂无可读 ETF 候选",
          怎么看: "先看融资现金线、待补原因和本地回放按钮",
          来源: source,
          风险核对: ordinaryMissingEvidence,
          边界: "缺数据时保持观察，不新增融资、不追高、不下单"
        }
      ];
  const detailItems: MetricItem[] = [
    { label: "本地快照", value: text(etfPacket.packet_role, "ETF/融资本地快照") },
    { label: "角色", value: text(etfPacket.packet_role, "ETF/融资配置证据") },
    { label: "验证", value: text(etfPacket.verification_status, "待验证"), tone: text(etfPacket.verification_status).includes("通过") ? "good" : "warn" },
    { label: "融资融券", value: marginStatus, tone: marginStatus === "ready" ? "good" : "warn" },
    { label: "来源", value: source },
    { label: "更新", value: text(etfPacket.updated_at, "暂无本地更新时间") }
  ];
  const snapshotIssueVisible = loading || Boolean(error) || (!loading && !error && !etfPacketLoaded && !marginPacketLoaded);
  const snapshotIssueTitle = loading ? "正在读取本地快照" : "本地快照待补";
  const snapshotIssueDetail = loading
    ? "正在读取 ETF/融资本地快照；页面不会自动刷新外部数据。"
    : error
      ? "没有读到 ETF/融资本地快照；按保守风险预算处理，不新增融资。"
      : "当前没有 ETF/融资本地快照；先看现金线和缺口，不把空结果当成低风险。";
  const snapshotIssueItems: MetricItem[] = [
    { label: "当前状态", value: snapshotIssueDetail },
    { label: "下一步", value: "需要更新时点击本地回放按钮；换标的回下一票雷达" },
    { label: "安全边界", value: "不自动补外部数据、不调用模型、不交易、不加融资" }
  ];

  return (
    <div data-ltg10-component-id="MarginEtf">
      <div className="page-head">
        <div>
          <h1 data-ltg10-route-heading="marginEtf">ETF / 融资</h1>
          <p>先看 ETF 候选、融资现金线、风险提示和下一步。</p>
        </div>
      </div>

      <PacketCard title="ETF / 融资操作台" subtitle="普通用户先看这里" status={ordinaryStatus}>
        {snapshotIssueVisible ? (
          <div className="page-state page-state-empty motion-surface" data-page-state="margin_etf_snapshot_issue" data-motion-scope="ordinary_user_margin_etf_clarity" data-motion-purpose="risk_snapshot_clarity">
            <strong>{snapshotIssueTitle}</strong>
            <p>{snapshotIssueDetail}</p>
            <MetricGrid items={snapshotIssueItems} />
          </div>
        ) : null}
        <div aria-label="margin etf app visible now summary">
          <h3>打开 app 能看到什么</h3>
          <p className="ordinary-status-note" aria-label="margin etf app visible now sentence" aria-live="polite">{marginEtfAppVisibleNowSentence}</p>
          <MetricGrid items={marginEtfAppVisibleNowItems} />
          <div className="actions" aria-label="margin etf app visible now local actions">
            <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from margin etf visible now">换标的</a>
            <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf visible now">看风险护栏</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from margin etf visible now">看数据能力</a>
            <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf visible now">今日作战台</a>
          </div>
          <p className="risk-note">这个条带只回答普通用户打开页面能看到什么：ETF 候选、融资现金线、来源层、缺口原因和下一步入口；普通链接只切换本地页面，不启动刷新流程、不刷新外部数据或模型、不交易、不加融资、不改交易策略。</p>
        </div>

        <div aria-label="margin etf candidate radar confirmed data bridge">
          <h3>确认结果承接</h3>
          <p className="ordinary-status-note" aria-label="margin etf candidate radar confirmed data bridge sentence" aria-live="polite">{marginEtfConfirmedDataBridgeSentence}</p>
          <MetricGrid items={marginEtfConfirmedDataBridgeItems} />
          <div className="actions" aria-label="margin etf candidate radar confirmed data bridge actions">
            <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；输入和读取不外联" aria-label="return candidate radar confirm input from margin etf data bridge">回确认输入</a>
            <a href="#factor/factor-score" title="切换到股票量化推演；只读本地回放" aria-label="open factor from margin etf data bridge">看量化推演</a>
            <a href="#next/next-session-chart" title="切换到次日图谱；只读本地回放" aria-label="open next session from margin etf data bridge">看次日图谱</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from margin etf data bridge">数据能力</a>
          </div>
          <p className="risk-note">承接卡只读下一票雷达已经写入的 cache / call_ledger / packet；不会因为打开 ETF/融资页而创建 task、调用 Tushare/DeepSeek、启动 worker、交易、加融资或改写 strategy action。</p>
        </div>

        <div aria-label="margin etf ordinary plain conclusion">
          <h3>普通结论</h3>
          <p className="ordinary-status-note" aria-label="margin etf ordinary plain conclusion sentence" aria-live="polite">{ordinaryPlainConclusion}</p>
          <MetricGrid items={ordinaryPlainItems} />
          <p className="risk-note">普通结论只读本地 ETF/融资快照；页面打开、查看结果和切换入口都不会启动刷新流程、刷新外部数据或模型、改写交易策略。</p>
        </div>

        <div aria-label="margin etf first viewport action strip">
          <h3>首屏下一步</h3>
          <p className="ordinary-status-note" aria-label="margin etf first viewport action sentence" aria-live="polite">{marginEtfFirstViewportActionSentence}</p>
          <MetricGrid items={marginEtfFirstViewportActionItems} />
          <div className="actions" aria-label="margin etf first viewport local links">
            <a href="#margin-etf-candidate-rows" title="跳到 ETF 候选行；只读本地快照" aria-label="open etf candidate rows from first viewport">看 ETF 候选</a>
            <a href="#margin-etf-cash-line" title="跳到融资现金线；只读本地快照" aria-label="open cash line from first viewport">看现金线</a>
            <a href="#margin-etf-local-refresh-actions" title="跳到下方本地回放按钮；不会自动点击或创建任务" aria-label="jump local refresh actions from first viewport">本地回放按钮</a>
            <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from first viewport action strip">换标的</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from first viewport action strip">数据能力</a>
          </div>
          <p className="risk-note">首屏操作条只做本地锚点跳转；不会自动刷新 ETF、不会调用外部数据、模型或远端检查、不会创建后台流程、不会交易或改写策略。</p>
        </div>

        <div id="margin-etf-cash-line" aria-label="margin etf cash line quick read">
          <h3>融资现金线怎么读</h3>
          <p className="ordinary-status-note" aria-label="margin etf cash line sentence" aria-live="polite">{marginEtfCashLineSentence}</p>
          <MetricGrid items={marginEtfCashLineItems} />
          <div className="actions" aria-label="margin etf cash line local actions">
            <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；候选不是买入指令" aria-label="return candidate radar from margin etf cash line">换标的</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from margin etf cash line">数据能力</a>
            <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf cash line">风险护栏</a>
          </div>
          <details className="developer-audit-details" aria-label="margin etf cash line rows">
            <summary>查看现金线读法</summary>
            <p className="risk-note">现金线读法只整理本地融资比例、建议比例、现金缓冲和缺口；不会刷新外部数据、不启动刷新流程、不交易、不改策略。</p>
            <DataLineageTable rows={marginEtfCashLineRows} />
          </details>
          <p className="risk-note">融资现金线只用于风险预算：缺数据按保守处理；ETF 强弱不能变成买入、加仓、加融资或下单指令。</p>
        </div>

        <div id="margin-etf-local-refresh-actions" className="actions" aria-label="margin etf primary actions">
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            title="只重新读取本地快照；不启动刷新流程、不刷新外部数据或模型"
            aria-label="refresh margin etf local readback"
          >重新读取本地快照</button>
          <button
            type="button"
            onClick={launchLocalRefreshTask}
            disabled={Boolean(taskDisabledReason) || taskSubmitting}
            title={taskDisabledReason || "启动本地 ETF/融资回放流程；不刷新外部数据或模型"}
            aria-label="start margin etf local refresh flow"
          >{taskSubmitting ? "生成中" : "生成本地回放"}</button>
          <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf">今日作战台</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；候选不是买入指令" aria-label="open candidate radar from margin etf">下一票雷达</a>
          <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf">风险护栏</a>
        </div>
        {taskDisabledReason && <p className="risk-note">刷新暂不可用：{ordinaryText(taskDisabledReason)}</p>}
        {taskDegradedReason && <p className="risk-note">{ordinaryText(taskDegradedReason)}</p>}
        {taskError && <p className="risk-note">{ordinaryText(taskError)}</p>}
        {(taskReceipt || taskSubmitting || taskError || taskId) ? (
          <div aria-label="margin etf local refresh result quick read">
            <h3>刷新后结果</h3>
            <p className="ordinary-status-note" aria-label="margin etf local refresh result summary" aria-live="polite">{ordinaryText(localRefreshReadableSummary)}</p>
            <MetricGrid items={localRefreshResultItems} />
          <p className="risk-note">这张结果摘要只读按钮返回的本地回执和本地记录；缺 ETF 或融资本地快照时只显示待补原因，不会补外部数据、调用模型、交易或改写策略。</p>
          </div>
        ) : null}
        {(taskReceipt || taskId) ? (
          <details className="developer-audit-details" aria-label="margin etf local refresh developer details">
            <summary>研究辅助 / 本地回放详情</summary>
            <p className="risk-note">这里才显示按钮返回的后台流程和回放明细；普通用户先看上方结果摘要。</p>
            <TaskLaunchReceipt receipt={taskReceipt} />
            <TaskStatusPanel taskId={taskId} onSuccess={refresh} />
          </details>
        ) : null}
        <p className="risk-note">{ordinaryText(boundary)}</p>

        <details className="developer-audit-details" aria-label="margin etf supporting read details">
          <summary>展开 ETF/融资更多读法</summary>
          <p className="risk-note">下面保留路径承接、运行模式和记录口径；默认收起，避免普通用户第一眼被长表淹没。</p>
          <div aria-label="margin etf first viewport risk summary card">
            <h3>ETF / 融资一屏风险卡</h3>
            <p className="ordinary-status-note" aria-label="margin etf first viewport risk sentence" aria-live="polite">{marginEtfFirstViewportRiskSentence}</p>
            <MetricGrid items={marginEtfFirstViewportRiskItems} />
            <p className="risk-note">这张风险卡只合成本地 ETF 候选、融资现金线和缺口；不启动刷新流程、不刷新外部数据或模型、不交易、不加融资。</p>
          </div>
          <MetricGrid items={summaryItems} />
          <div aria-label="margin etf ordinary first screen quick read">
            <h3>现在能看什么</h3>
            <p className="ordinary-status-note" aria-label="margin etf ordinary quick read summary" aria-live="polite">{ordinaryText(ordinaryQuickReadSummary)}</p>
            <MetricGrid items={ordinaryQuickReadItems} />
            <p className="risk-note">这张速读只读本地 ETF/融资快照和本地融资状态；不会启动刷新流程、不会调用外部数据或模型服务、不会交易或改写策略。</p>
          </div>
          <div aria-label="margin etf post research risk path">
            <h3>确认结果后查风险预算</h3>
            <p className="ordinary-status-note" aria-label="margin etf post research risk path sentence" aria-live="polite">{marginEtfPostResearchRiskPathSentence}</p>
            <MetricGrid items={marginEtfPostResearchRiskPathItems} />
            <div className="actions" aria-label="margin etf post research risk path actions">
              <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读本地结果" aria-label="open factor from margin etf post research path">看量化推演</a>
              <a href="#next/next-session-chart" title="切换到次日图谱；只读本地结果" aria-label="open next from margin etf post research path">看次日图谱</a>
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据、权限、空窗口和本地结果状态" aria-label="open data capability from margin etf post research path">数据能力</a>
              <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from margin etf post research path">换标的</a>
              <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf post research path">风险护栏</a>
            </div>
            <details className="developer-audit-details" aria-label="margin etf post research risk path rows">
              <summary>查看结果到风险预算路径</summary>
              <p className="risk-note">这张路径表只说明从量化推演或次日图谱到 ETF/融资风险预算怎么读；不启动刷新流程、不刷新外部数据或模型、不交易。</p>
              <DataLineageTable rows={marginEtfPostResearchRiskPathRows} />
            </details>
            <p className="risk-note">确认结果后的风险预算只读本地快照：ETF 候选不是买入，融资比例不是加杠杆许可，缺数据按保守处理。</p>
          </div>
          <div aria-label="margin etf candidate radar risk budget bridge">
            <h3>从候选页过来怎么看</h3>
            <p className="ordinary-status-note" aria-label="margin etf candidate bridge sentence" aria-live="polite">{marginEtfCandidateBridgeSentence}</p>
            <MetricGrid items={marginEtfCandidateBridgeItems} />
            <div className="actions" aria-label="margin etf candidate bridge local actions">
              <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；候选不是买入指令" aria-label="return candidate radar from margin etf bridge">回下一票雷达</a>
              <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf bridge">看风险护栏</a>
              <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf bridge">今日作战台</a>
            </div>
            <details className="developer-audit-details" aria-label="margin etf candidate bridge rows">
              <summary>查看承接顺序</summary>
              <p className="risk-note">承接顺序只说明候选页、ETF/融资和风险护栏怎么读；不读取外部数据，不启动刷新流程，不生成交易动作。</p>
              <DataLineageTable rows={marginEtfCandidateBridgeRows} />
            </details>
            <p className="risk-note">这张承接卡只读本地 ETF/融资快照；普通链接只切换本地页面，不刷新外部数据、不启动刷新流程、不交易、不改策略。</p>
          </div>
          <div aria-label="margin etf ordinary risk card">
            <h3>ETF / 融资风险卡</h3>
            <p className="ordinary-status-note" aria-label="margin etf ordinary risk card summary" aria-live="polite">{marginEtfRiskCardStatus}</p>
            <MetricGrid items={marginEtfRiskCardItems} />
            <details className="developer-audit-details" aria-label="margin etf ordinary risk card rows">
              <summary>风险复核顺序</summary>
              <p className="risk-note">这张明细只整理本地 ETF 候选、融资现金线和缺口；不读取外部数据，不启动刷新流程，不把候选变成交易动作。</p>
              <DataLineageTable rows={marginEtfRiskCardRows} />
            </details>
            <p className="risk-note">风险卡只读本地 ETF/融资快照；ETF 候选不是买入指令，融资比例不是加杠杆许可，缺数据时按保守处理。</p>
          </div>
          <div aria-label="margin etf mode layered live light boundary">
            <h3>运行模式分层</h3>
            <p className="ordinary-status-note">把本地快照、按钮刷新、数据证据、旧入口退场和交易隔离分开看；live_light 也只能是可审计后台流程，不是页面渲染外联。</p>
            <MetricGrid items={modeLayerItems} />
          </div>
          <p className="ordinary-status-note">{text(etfPacket.evidence_summary, text(etfPacket.summary, "暂无 ETF/融资快照；先保留观察，不新增融资。"))}</p>
        </details>
      </PacketCard>

      {snapshotIssueVisible ? (
        <PacketCard title={snapshotIssueTitle} subtitle="普通风险快照" status={loading ? "读取中" : "待补"}>
          <p className="ordinary-status-note">{snapshotIssueDetail}</p>
          <MetricGrid items={snapshotIssueItems} />
          <p className="risk-note">本页只读取本地快照；不会在页面打开时自动发现 ETF、拉行情或调用模型。</p>
        </PacketCard>
      ) : null}

      <PacketCard title="ETF 候选分组" subtitle="推荐、观察、回避和排除分开看" status={noEtfRows ? "候选待补" : "候选可读"}>
        <div id="margin-etf-candidate-rows" aria-label="margin etf candidate row reading guide">
          <h3>每行怎么读</h3>
          <p className="ordinary-status-note" aria-label="margin etf candidate row reading summary" aria-live="polite">{marginEtfCandidateReadingSummary}</p>
          <MetricGrid items={marginEtfCandidateReadingItems} />
          <details className="developer-audit-details" aria-label="margin etf candidate row reading rows">
            <summary>查看逐行读法</summary>
            <p className="risk-note">逐行读法只重排本地候选行的状态、理由、来源、流动性、重叠和现金/杠杆；不刷新外部数据、不启动刷新流程、不交易。</p>
            <DataLineageTable rows={marginEtfCandidateReadingRows} />
          </details>
          <p className="risk-note">读法卡只帮助普通用户看懂已有 ETF 行；推荐不是买入，观察不是加仓，回避/排除不是反向交易信号。</p>
        </div>
        <DataLineageTable rows={allVisibleEtfRows} />
        <p className="risk-note">每行先看来源、状态、理由、流动性、同类重叠、融资现金线（现金/杠杆）和边界。推荐只表示优先复核；观察等待触发条件；回避/排除不能拿来追高。所有 ETF 行都不是买入、加仓或加融资指令。</p>
      </PacketCard>

      <PacketCard title="融资现金线" subtitle="先决定能不能新增风险，再看 ETF 强弱" status={allowNewMargin ? "小额待条件" : "不新增融资"}>
        <MetricGrid items={detailItems} />
        <DataLineageTable rows={riskRows} />
      </PacketCard>

      <details className="developer-audit-details" aria-label="margin etf audit details">
        <summary>研究辅助 / 审计详情</summary>
        <p className="risk-note">这里仅用于排查本地快照来源、warning 和读取记录；不展示 token/key，不触发外部刷新。</p>
        <DataLineageTable rows={warnings.map((warning, index) => ({ 序号: index + 1, warning }))} />
        <DataLineageTable rows={callLedger} />
      </details>
    </div>
  );
}
