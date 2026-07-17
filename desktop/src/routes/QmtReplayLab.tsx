import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCandidateRadarCache,
  getNextSessionCache,
  getQmtReplayCache,
  postQmtLocalReplay,
  type QmtReplayScenario,
  type TaskCreationEnvelope
} from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import PageStateBanner from "../components/PageStateBanner";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";
import {
  evaluateQmtReplayOrdinaryGate,
  strictQmtDate,
  strictQmtId,
  strictQmtScope,
  strictQmtSymbol,
} from "./qmtReplayOrdinaryGate";

type Row = Record<string, unknown>;
type ReplayFrameCount = 12 | 24 | 48;
type ResearchState = "observe" | "watch" | "excluded";

const REPLAY_SCENARIOS: Array<{ value: QmtReplayScenario; label: string; detail: string }> = [
  { value: "baseline", label: "基准观察", detail: "按当前本地缓存顺序回放，不生成交易动作。" },
  { value: "stress", label: "压力复核", detail: "放大缺口和失效条件，只作研究复核。" },
  { value: "recovery", label: "恢复路径", detail: "观察证据恢复顺序，不连接账户或券商。" }
];

const FRAME_OPTIONS: ReplayFrameCount[] = [12, 24, 48];
const ALLOWED_RESEARCH_STATES = new Set<ResearchState>(["observe", "watch", "excluded"]);

function asObject(value: unknown): Row {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Row) : {};
}

function asRows(value: unknown): Row[] {
  return Array.isArray(value) ? value.filter((row): row is Row => Boolean(row && typeof row === "object" && !Array.isArray(row))) : [];
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    const text = typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
    if (text) return text;
  }
  return "";
}

function safeDemoLabel(value: string): string {
  return value.replace(/[^\p{L}\p{N}\s._-]/gu, "").trim().slice(0, 32);
}

function researchState(value: unknown): ResearchState {
  const normalized = String(value ?? "").trim().toLowerCase() as ResearchState;
  return ALLOWED_RESEARCH_STATES.has(normalized) ? normalized : "excluded";
}

function statusTone(status: string): "good" | "warn" | "bad" | "neutral" {
  const normalized = status.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (/blocked|failed|mismatch|unsafe|error|invalid/.test(normalized)) return "bad";
  if (/not_ready|not_available|pending|missing|waiting|empty|unknown|degraded/.test(normalized)) return "warn";
  if (new Set(["ready", "success", "succeeded", "passed", "match", "preserved", "fresh"]).has(normalized)) return "good";
  return "neutral";
}

function researchStateLabel(state: ResearchState): string {
  if (state === "observe") return "观察";
  if (state === "watch") return "关注";
  return "排除";
}

export default function QmtReplayLab() {
  const [qmtCache, setQmtCache] = useState<Row>({});
  const [candidateCache, setCandidateCache] = useState<Row>({});
  const [nextSessionCache, setNextSessionCache] = useState<Row>({});
  const [candidateEnvelopeLedger, setCandidateEnvelopeLedger] = useState<Row[]>([]);
  const [nextEnvelopeLedger, setNextEnvelopeLedger] = useState<Row[]>([]);
  const [qmtEnvelopeLedger, setQmtEnvelopeLedger] = useState<Row[]>([]);
  const [candidateWarnings, setCandidateWarnings] = useState<string[]>([]);
  const [nextWarnings, setNextWarnings] = useState<string[]>([]);
  const [qmtWarnings, setQmtWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [cacheError, setCacheError] = useState("");
  const [scenario, setScenario] = useState<QmtReplayScenario>("baseline");
  const [maxFrames, setMaxFrames] = useState<ReplayFrameCount>(24);
  const [demoLabel, setDemoLabel] = useState("本地演示");
  const [approved, setApproved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);

  const refreshCache = useCallback(() => {
    setLoading(true);
    setCacheError("");
    void Promise.all([getQmtReplayCache(), getCandidateRadarCache(), getNextSessionCache()])
      .then(([qmtResult, candidateResult, nextSessionResult]) => {
        setQmtCache(qmtResult.data ?? {});
        setCandidateCache(candidateResult.data ?? {});
        setNextSessionCache(nextSessionResult.data ?? {});
        setCandidateEnvelopeLedger(candidateResult.call_ledger ?? []);
        setNextEnvelopeLedger(nextSessionResult.call_ledger ?? []);
        setQmtEnvelopeLedger(qmtResult.call_ledger ?? []);
        setCandidateWarnings(candidateResult.warnings ?? []);
        setNextWarnings(nextSessionResult.warnings ?? []);
        setQmtWarnings(qmtResult.warnings ?? []);
        if (!qmtResult.ok) setCacheError(qmtResult.error ?? "qmt_replay_cache_not_ready");
        else if (!candidateResult.ok) setCacheError(candidateResult.error ?? "candidate_cache_not_ready");
        else if (!nextSessionResult.ok) setCacheError(nextSessionResult.error ?? "next_session_cache_not_ready");
      })
      .catch((error) => setCacheError(error instanceof Error ? error.message : String(error)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refreshCache();
  }, [refreshCache]);

  const candidateV05Lineage = asObject(candidateCache.candidate_radar_v05_next_session_lineage);
  const nextSessionV05Lineage = asObject(nextSessionCache.candidate_radar_v05_lineage);
  const qmtSourceLineage = asObject(qmtCache.source_lineage);
  const safetyBoundary = asObject(qmtCache.safety_boundary);
  const replaySummary = asObject(qmtCache.replay);
  const payloadCallLedger = asRows(qmtCache.call_ledger);
  const currentResult = Object.keys(asObject(qmtCache.current_result)).length
    ? asObject(qmtCache.current_result)
    : asObject(qmtCache.current_result_summary);
  const lastGoodResult = Object.keys(asObject(qmtCache.last_good_result)).length
    ? asObject(qmtCache.last_good_result)
    : asObject(qmtCache.last_good_result_summary);

  const qmtGate = evaluateQmtReplayOrdinaryGate({
    loading,
    error: cacheError,
    candidate: candidateCache,
    candidateWarnings,
    candidateLedger: candidateEnvelopeLedger,
    nextSession: nextSessionCache,
    nextWarnings,
    nextLedger: nextEnvelopeLedger,
    qmt: qmtCache,
    qmtWarnings,
    qmtLedger: qmtEnvelopeLedger,
  });
  const candidateSymbol = qmtGate.symbol;
  const candidateTaskId = qmtGate.taskId;
  const candidateResultVersion = qmtGate.resultVersion;
  const candidateScopeHash = qmtGate.scopeHash;
  const candidateDataDate = qmtGate.dataDate;
  const candidateFreshnessState = asObject(candidateV05Lineage.freshness_state);
  const candidateFreshness = typeof candidateFreshnessState.state === "string"
    ? candidateFreshnessState.state
    : "unknown";
  const candidateExpectedTradeDate = strictQmtDate(candidateFreshnessState.expected_trade_date);
  const candidateDateReady = qmtGate.lineageReady;
  const nextSymbol = strictQmtSymbol(nextSessionV05Lineage.symbol);
  const nextTaskId = strictQmtId(nextSessionV05Lineage.candidate_task_id);
  const nextResultVersion = strictQmtId(nextSessionV05Lineage.candidate_result_version);
  const nextScopeHash = strictQmtScope(nextSessionV05Lineage.candidate_scope_hash);
  const nextDataDate = strictQmtDate(nextSessionV05Lineage.data_date);
  const qmtSourceSymbol = strictQmtSymbol(qmtSourceLineage.source_symbol);
  const qmtSourceTaskId = strictQmtId(qmtSourceLineage.source_task_id);
  const qmtSourceResultVersion = strictQmtId(qmtSourceLineage.source_result_version);
  const qmtSourceScopeHash = strictQmtScope(qmtSourceLineage.source_scope_hash);
  const symbolMatches = Boolean(candidateSymbol && candidateSymbol === nextSymbol);
  const taskMatches = Boolean(candidateTaskId && candidateTaskId === nextTaskId);
  const resultVersionMatches = Boolean(candidateResultVersion && candidateResultVersion === nextResultVersion);
  const scopeMatches = Boolean(candidateScopeHash && candidateScopeHash === nextScopeHash);
  const dataDateMatches = Boolean(candidateDataDate && candidateDataDate === nextDataDate);

  const qmtConnected = ["qmt_called", "qmt_external_connection_attempted", "qmt_process_discovered", "qmt_client_imported", "xtquant_imported"]
    .some((field) => safetyBoundary[field] === true);
  const brokerConnected = safetyBoundary.broker_called === true || safetyBoundary.broker_session_opened === true;
  const accountBound = safetyBoundary.account_query_executed === true;
  const orderEndpointPresent = safetyBoundary.real_order_submitted === true || safetyBoundary.real_order_cancelled === true;
  const ordersCreated = typeof safetyBoundary.real_order_count === "number" ? safetyBoundary.real_order_count : Number.NaN;
  const externalCallsTriggered = safetyBoundary.external_calls_triggered === true || safetyBoundary.external_call_count !== 0;
  const executesTrades = safetyBoundary.does_not_execute_trades === false || safetyBoundary.real_trade_executed === true;
  const modifiesStrategyAction = safetyBoundary.does_not_modify_strategy_action === false;
  const unsafeBoundary = qmtConnected || brokerConnected || accountBound || orderEndpointPresent ||
    (Number.isFinite(ordersCreated) && ordersCreated > 0) || externalCallsTriggered || executesTrades || modifiesStrategyAction ||
    safetyBoundary.provider_called === true || safetyBoundary.model_called === true || safetyBoundary.worker_dispatched === true;
  const safetyExplicitSafe = qmtGate.safetyReady && qmtGate.ledgersReady && !unsafeBoundary;
  const safetyUnknown = !unsafeBoundary && !safetyExplicitSafe;
  const lineageReady = qmtGate.lineageReady;
  const qmtResultBound = qmtGate.resultReady;

  const rawVirtualEventsUnbound = asRows(qmtCache.virtual_research_events).length
    ? asRows(qmtCache.virtual_research_events)
    : asRows(currentResult.virtual_research_events).length
      ? asRows(currentResult.virtual_research_events)
      : asRows(replaySummary.virtual_research_events).length
        ? asRows(replaySummary.virtual_research_events)
        : asRows(replaySummary.research_events);
  const rawVirtualEvents = qmtResultBound ? rawVirtualEventsUnbound : [];
  const virtualResearchEvents = useMemo(
    () =>
      rawVirtualEvents.slice(0, 120).map((event, index) => ({
        frame: Number(event.frame ?? event.index ?? index + 1),
        label: firstText(event.label, event.name, `研究帧 ${index + 1}`),
        research_state: researchState(event.research_state ?? event.event ?? event.state),
        reference_value: event.reference_value ?? event.value ?? "--",
        evidence: firstText(event.evidence, event.reason, "本地缓存研究证据"),
        boundary: firstText(event.boundary, "仅作研究回放；不连接 QMT、券商或订单接口")
      })),
    [rawVirtualEvents]
  );

  const lineageRows: Row[] = [
    {
      check: "标的",
      candidate: candidateSymbol || "待 Candidate v0.5 cache",
      next_session: nextSymbol || "待 Next Session lineage",
      qmt_cache: qmtSourceSymbol || "首次回放前可为空",
      status: symbolMatches && (!qmtSourceSymbol || qmtSourceSymbol === candidateSymbol) ? "match" : "blocked"
    },
    {
      check: "源任务",
      candidate: candidateTaskId || "待 Candidate v0.5 cache",
      next_session: nextTaskId || "待 Next Session lineage",
      qmt_cache: qmtSourceTaskId || "首次回放前可为空",
      status: taskMatches && (!qmtSourceTaskId || qmtSourceTaskId === candidateTaskId) ? "match" : "blocked"
    },
    {
      check: "结果版本",
      candidate: candidateResultVersion || "待 Candidate v0.5 cache",
      next_session: nextResultVersion || "待 Next Session lineage",
      qmt_cache: qmtSourceResultVersion || "首次回放前可为空",
      status: resultVersionMatches && (!qmtSourceResultVersion || qmtSourceResultVersion === candidateResultVersion) ? "match" : "blocked"
    },
    {
      check: "范围哈希",
      candidate: candidateScopeHash ? candidateScopeHash.slice(0, 12) : "待 Candidate v0.5 cache",
      next_session: nextScopeHash ? nextScopeHash.slice(0, 12) : "待 Next Session lineage",
      qmt_cache: qmtSourceScopeHash ? qmtSourceScopeHash.slice(0, 12) : "首次回放前可为空",
      status: scopeMatches && (!qmtSourceScopeHash || qmtSourceScopeHash === candidateScopeHash) ? "match" : "blocked"
    },
    {
      check: "数据日期",
      candidate: candidateDataDate || "待 Candidate data_date",
      next_session: nextDataDate || "待 Next Session data_date",
      qmt_cache: candidateExpectedTradeDate || "待交易日历",
      status: dataDateMatches && candidateDateReady ? "match" : "blocked"
    }
  ];

  const scenarioDetail = REPLAY_SCENARIOS.find((item) => item.value === scenario)?.detail ?? "本地研究回放";
  const launchAllowed = approved && qmtGate.launchReady && !submitting;
  const gateBlocker: Record<string, string> = {
    loading_or_error: loading ? "正在读取本地证据，请稍候。" : "本地证据读取失败，已停止生成。",
    warning_present: "本地来源仍有真实警告，已停止生成；固定说明不会计入警告。",
    ledger_invalid: "读取审计不完整，无法证明三个来源都保持本地只读。",
    source_contract_invalid: "Candidate 或 Next Session 来源合同不完整，已停止生成。",
    lineage_mismatch: "Candidate 与 Next Session 不是同一份来源结果，已停止生成。",
    qmt_packet_invalid: "QMT 本地缓存合同不完整，已停止生成。",
    qmt_safety_invalid: "安全边界字段不完整或存在异常，已停止生成。",
  };
  const launchBlocker = unsafeBoundary
    ? "安全边界异常：检测到连接、账户、订单接口或交易动作声明。"
    : safetyUnknown
      ? "安全证据不完整：必须明确证明无外部连接、无账户、无订单和无交易动作。"
    : !qmtGate.launchReady
      ? gateBlocker[qmtGate.reasonKey] ?? "等待三份本地来源完成严格核对。"
      : !approved
        ? "请先确认本次仅运行本地研究回放。"
        : "";

  const launchReplay = () => {
    if (!launchAllowed) return;
    setSubmitting(true);
    setSubmitError("");
    const normalizedDemoLabel = safeDemoLabel(demoLabel);
    void postQmtLocalReplay({
      approved_by_user: true,
      mode: "local_research_replay",
      scenario,
      max_frames: maxFrames,
      source_symbol: candidateSymbol,
      source_task_id: candidateTaskId,
      source_result_version: candidateResultVersion,
      source_scope_hash: candidateScopeHash,
      source_data_date: candidateDataDate,
      ...(normalizedDemoLabel ? { demo_label: normalizedDemoLabel } : {})
    })
      .then((result) => {
        setTaskReceipt(result);
        if (result.ok) {
          setTaskId(result.data.task_id);
          setApproved(false);
        } else {
          setSubmitError(result.error ?? "qmt_local_replay_task_not_accepted");
        }
      })
      .catch((error) => setSubmitError(error instanceof Error ? error.message : String(error)))
      .finally(() => setSubmitting(false));
  };

  const displayLedger = [
    ...candidateEnvelopeLedger,
    ...nextEnvelopeLedger,
    ...qmtEnvelopeLedger,
    ...payloadCallLedger,
  ];
  const warningRows = [...candidateWarnings, ...nextWarnings, ...qmtWarnings]
    .map((warning, index) => ({ index: index + 1, warning }));
  const cacheStatus = firstText(qmtCache.status, "cache_missing");
  const visibleResearchEvents = virtualResearchEvents.slice(0, 8);
  const sourceVersionLabel = candidateResultVersion
    ? candidateResultVersion.length > 18
      ? `${candidateResultVersion.slice(0, 10)}…${candidateResultVersion.slice(-5)}`
      : candidateResultVersion
    : "等待本地结果";
  const resultState = submitError
    ? "本次未生成"
    : submitting
      ? "正在生成本地演示"
      : taskReceipt?.ok
        ? "本地演示已接收"
        : virtualResearchEvents.length
          ? "已有本地回放"
          : rawVirtualEventsUnbound.length
            ? "历史回放已隔离"
          : "等待生成";
  const nextStep = unsafeBoundary
    ? "已停止：安全隔离异常，请先查看技术详情。"
    : safetyUnknown
      ? "已停止：安全证据不完整，不能把未知状态解释成未连接。"
    : !qmtGate.launchReady
      ? gateBlocker[qmtGate.reasonKey] ?? "先回到下一票雷达，生成同一标的、同一版本的本地结果。"
      : rawVirtualEventsUnbound.length && !qmtResultBound
        ? "旧回放与当前来源不完全一致，已从普通视图隔离；可在确认边界后生成同源演示。"
      : virtualResearchEvents.length
        ? "按时间线复核观察、关注与排除理由；它们不是交易指令。"
        : "选择场景和帧数，确认本地边界后生成一份研究演示。";

  return (
    <div className="qmt-product-shell" data-ltg10-component-id="QmtReplayLab">
      <div className="page-head qmt-product-hero">
        <div>
          <p className="qmt-product-kicker">RESEARCH REPLAY · LOCAL ONLY</p>
          <h1 data-ltg10-route-heading="qmt-replay">QMT 本地回放</h1>
          <p className="qmt-product-lede">把一次本地研究判断按时间展开，复核来源、状态变化与下一步；全程不触达交易系统。</p>
        </div>
        <span className={`qmt-product-state ${unsafeBoundary || safetyUnknown ? "is-blocked" : lineageReady ? "is-ready" : "is-waiting"}`}>
          {unsafeBoundary ? "安全停止" : safetyUnknown ? "安全证据待确认" : lineageReady ? "本地来源已核对" : "等待同源数据"}
        </span>
      </div>

      <section
        className="qmt-safety-boundary motion-surface"
        role="status"
        aria-label="QMT permanent research only safety boundary"
        data-qmt-permanent-safety-boundary="true"
        data-qmt-ordinary-block="safety"
        data-motion-purpose="state_change_confirmation"
      >
        <span className="qmt-safety-mark" aria-hidden="true">LOCAL</span>
        <div>
          <strong>
            {unsafeBoundary
              ? "检测到安全边界异常｜已停止本地回放"
              : safetyUnknown
                ? "连接与交易隔离证据不完整｜已停止本地回放"
                : "QMT未调用｜券商未调用｜无账户查询｜无真实订单｜仅本地研究回放"}
          </strong>
          <p>
            {safetyExplicitSafe
              ? "当前证据明确表明：未探测或调用 QMT、券商与账户，未创建真实订单、交易或持仓变更。"
              : "只有隔离字段和本地审计记录全部明确安全时才会启用；缺失或未知不会被解释成安全。"}
          </p>
        </div>
      </section>

      <PageStateBanner
        loading={loading}
        error={cacheError ? "本地回放暂不可用，请稍后重试或展开技术详情查看原因。" : ""}
        empty={!loading && !candidateSymbol && !virtualResearchEvents.length}
        emptyTitle="暂无可回放的 Candidate v0.5 血缘"
        emptyDetail="请先在下一票雷达生成本地 v0.5 结果；本页 GET 不创建任务、不连接 QMT。"
      />

      <section className="qmt-product-section qmt-source-panel" data-qmt-ordinary-block="source">
        <div className="qmt-section-heading">
          <div>
            <p className="qmt-section-index">01 · 本地来源</p>
            <h2>{candidateSymbol || "等待下一票雷达结果"}</h2>
          </div>
          <span className={lineageReady ? "qmt-source-check is-ready" : "qmt-source-check"}>
            {lineageReady ? "同源与日期已核对" : "等待同源"}
          </span>
        </div>
        <div className="qmt-source-facts" aria-label="本地回放来源与版本">
          <div><span>结果版本</span><strong>{sourceVersionLabel}</strong></div>
          <div><span>数据日期</span><strong>{candidateDataDate || "待本地数据"}</strong></div>
          <div><span>数据状态</span><strong>{candidateDateReady ? "日期已验证" : "需要复核"}</strong></div>
        </div>
        <p className="qmt-source-note">只在标的、任务、结果版本、范围、交易日历和数据日期全部同源时启用本地回放；缺口不会被解释成安全。</p>
        <div className="qmt-local-links" aria-label="QMT replay local read only source links">
          <a href="#candidates" aria-label="打开下一票雷达本地来源">查看来源</a>
          <a href="#next/next-session-chart" aria-label="打开次日图谱本地血缘">查看次日图谱</a>
        </div>
      </section>

      <section className="qmt-product-section qmt-control-panel" data-qmt-ordinary-block="controls" id="qmt-replay-operator">
        <div className="qmt-section-heading">
          <div>
            <p className="qmt-section-index">02 · 生成演示</p>
            <h2>选择研究场景</h2>
          </div>
          <p>输入和切换只保存在当前页面，POST=0。</p>
        </div>
        <div className="qmt-control-layout">
          <div className="qmt-replay-controls">
            <label htmlFor="qmt-replay-scenario">
              研究场景
              <select id="qmt-replay-scenario" value={scenario} onChange={(event) => setScenario(event.target.value as QmtReplayScenario)}>
                {REPLAY_SCENARIOS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label htmlFor="qmt-replay-max-frames">
              最大研究帧
              <select id="qmt-replay-max-frames" value={maxFrames} onChange={(event) => setMaxFrames(Number(event.target.value) as ReplayFrameCount)}>
                {FRAME_OPTIONS.map((value) => <option value={value} key={value}>{value} 帧</option>)}
              </select>
            </label>
            <label htmlFor="qmt-replay-demo-label">
              脱敏演示标签
              <input
                id="qmt-replay-demo-label"
                value={demoLabel}
                maxLength={32}
                onChange={(event) => setDemoLabel(event.target.value)}
                aria-describedby="qmt-replay-input-boundary"
              />
            </label>
          </div>
          <div className="qmt-launch-panel">
            <p id="qmt-replay-input-boundary" className="qmt-scenario-copy">{scenarioDetail} 输入、选择、Tab 和页面渲染均 POST=0。</p>
            <label className="qmt-replay-confirm" htmlFor="qmt-replay-approved">
              <input
                id="qmt-replay-approved"
                type="checkbox"
                checked={approved}
                onChange={(event) => setApproved(event.target.checked)}
              />
              我确认：仅运行本地研究回放，不连接 QMT、券商或账户，不产生订单或真实交易。
            </label>
            <button
              type="button"
              className="qmt-replay-launch"
              disabled={!launchAllowed}
              onClick={launchReplay}
              aria-describedby="qmt-replay-launch-boundary"
            >
              {submitting ? "正在生成本地演示…" : "运行本地研究回放（不连接 QMT）"}
            </button>
            <p id="qmt-replay-launch-boundary" className="qmt-launch-note">{launchBlocker || "只生成一份本地研究演示；不调用 provider、model、QMT、券商或交易路径。"}</p>
            {submitError ? <p className="qmt-error-note" role="alert">本次未生成，请展开技术详情查看原因。</p> : null}
          </div>
        </div>
      </section>

      <section className="qmt-product-section qmt-timeline-panel" data-qmt-ordinary-block="timeline">
        <div className="qmt-section-heading">
          <div>
            <p className="qmt-section-index">03 · 事件时间线</p>
            <h2>研究状态如何变化</h2>
          </div>
          <p>仅包含观察、关注、排除；不是订单、成交或持仓动作。</p>
        </div>
        <div
          className="qmt-replay-track chart-refresh-frame"
          role="region"
          tabIndex={0}
          aria-label="QMT local virtual research event track"
          aria-describedby="qmt-replay-track-hint"
          data-qmt-replay-event-count={virtualResearchEvents.length}
        >
          {visibleResearchEvents.length ? (
            <ol>
              {visibleResearchEvents.map((event) => (
                <li data-research-state={event.research_state} key={`${event.frame}-${event.label}`}>
                  <span className="qmt-event-frame">{String(event.frame).padStart(2, "0")}</span>
                  <div>
                    <strong>{researchStateLabel(event.research_state)}</strong>
                    <small>{event.label}</small>
                  </div>
                </li>
              ))}
            </ol>
          ) : <p className="empty-state">尚未点击运行；空结果不表示无风险。</p>}
        </div>
        <p id="qmt-replay-track-hint" className="qmt-timeline-hint">该区域可用键盘聚焦；颜色只作辅助。下方表格提供等价文本，不依赖 hover 或颜色理解。</p>
        {visibleResearchEvents.length ? (
          <div className="qmt-timeline-table-wrap">
            <table className="qmt-timeline-table">
              <caption className="sr-only">本地研究事件等价文本</caption>
              <thead><tr><th>帧</th><th>状态</th><th>说明</th></tr></thead>
              <tbody>
                {visibleResearchEvents.map((event) => (
                  <tr key={`text-${event.frame}-${event.label}`}>
                    <td>{event.frame}</td><td>{researchStateLabel(event.research_state)}</td><td>{event.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="qmt-product-section qmt-result-panel" data-qmt-ordinary-block="result" aria-live="polite">
        <div className="qmt-section-heading">
          <div>
            <p className="qmt-section-index">04 · 结果与下一步</p>
            <h2>{resultState}</h2>
          </div>
          <span className="qmt-result-count">{virtualResearchEvents.length}<small>研究帧</small></span>
        </div>
        <p className="qmt-next-step">{nextStep}</p>
        {taskReceipt?.ok ? <p className="qmt-result-receipt task-panel--receipt">本地研究演示已接收，结果会在当前页面更新。</p> : null}
        <div className="qmt-result-facts">
          <span>本地缓存</span><span>研究状态</span><span>不产生交易动作</span>
        </div>
      </section>

      <details className="qmt-technical-details developer-audit-details">
        <summary><span>技术详情</span><small>血缘、回执、状态、原始帧与审计</small></summary>
        <div className="qmt-technical-stack">
          <p>GET /api/qmt-replay/cache、Candidate v0.5 和 Next Session 只读回放；页面不导入 QMT SDK、不探测进程/端口。</p>
          {cacheError || submitError ? <DataLineageTable rows={[{ cache_error: cacheError || "--", submit_error: submitError || "--" }]} /> : null}
          <MetricGrid
            items={[
              { label: "隔离证据", value: unsafeBoundary ? "异常" : safetyUnknown ? "未知" : "明确安全", tone: unsafeBoundary ? "bad" : safetyUnknown ? "warn" : "good" },
              { label: "QMT", value: qmtConnected ? "检测到调用或连接" : safetyExplicitSafe ? "明确未调用" : "未知", tone: qmtConnected ? "bad" : safetyExplicitSafe ? "good" : "warn" },
              { label: "券商", value: brokerConnected ? "检测到调用或会话" : safetyExplicitSafe ? "明确未调用" : "未知", tone: brokerConnected ? "bad" : safetyExplicitSafe ? "good" : "warn" },
              { label: "账户查询", value: accountBound ? "存在" : safetyExplicitSafe ? "明确无" : "未知", tone: accountBound ? "bad" : safetyExplicitSafe ? "good" : "warn" },
              { label: "真实订单", value: orderEndpointPresent ? "存在" : safetyExplicitSafe ? "明确无" : "未知", tone: orderEndpointPresent ? "bad" : safetyExplicitSafe ? "good" : "warn" },
              { label: "真实订单数", value: Number.isFinite(ordersCreated) ? ordersCreated : "未知", tone: Number.isFinite(ordersCreated) ? ordersCreated > 0 ? "bad" : "good" : "warn" },
              { label: "血缘校验", value: lineageReady ? "同源" : "阻断", tone: lineageReady ? "good" : "bad" },
              { label: "当前标的", value: candidateSymbol || "--" },
              { label: "数据日期", value: candidateDataDate || "--" },
              { label: "freshness", value: candidateFreshness, tone: candidateDateReady ? "good" : "warn" },
              { label: "研究帧", value: virtualResearchEvents.length },
              { label: "外部调用", value: externalCallsTriggered ? "存在" : safetyExplicitSafe ? "明确无" : "未知", tone: externalCallsTriggered ? "bad" : safetyExplicitSafe ? "good" : "warn" },
              { label: "真实交易", value: executesTrades ? "边界异常" : safetyExplicitSafe ? "明确禁止" : "未知", tone: executesTrades ? "bad" : safetyExplicitSafe ? "good" : "warn" }
            ]}
          />
          <PacketCard title="同源校验" subtitle="Candidate 与 Next 四项同源且日期验证后才允许生成；历史回放还须四项严格绑定" status={lineageReady ? "passed" : "blocked"}>
            <DataLineageTable rows={lineageRows} />
          </PacketCard>
          <TaskLaunchReceipt receipt={taskReceipt} />
          <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
          <PacketCard title="原始研究帧" subtitle="完整 schema 文本；只允许 observe / watch / excluded" status={virtualResearchEvents.length ? "local_replay_ready" : "waiting_for_explicit_replay"}>
            <DataLineageTable rows={virtualResearchEvents} />
          </PacketCard>
          <div className="grid">
            <PacketCard title="当前本地结果" subtitle="显式按钮任务写回；GET 只读" status={firstText(currentResult.status, replaySummary.status, "missing")}>
              <DataLineageTable rows={Object.keys(currentResult).length ? [currentResult] : []} />
            </PacketCard>
            <PacketCard title="上次成功结果" subtitle="失败不得覆盖 last-good" status={Object.keys(lastGoodResult).length ? "preserved" : "not_available"}>
              <DataLineageTable rows={Object.keys(lastGoodResult).length ? [lastGoodResult] : []} />
            </PacketCard>
          </div>
          <PacketCard title="本地读取审计" subtitle="call ledger / warnings / raw status" status={cacheStatus}>
            <StatusBadge label={unsafeBoundary ? "safety_blocked" : safetyUnknown ? "safety_unknown" : cacheStatus} tone={unsafeBoundary ? "bad" : safetyUnknown ? "warn" : statusTone(cacheStatus)} />
            <DataLineageTable rows={displayLedger} />
            <DataLineageTable rows={warningRows} />
          </PacketCard>
        </div>
      </details>
    </div>
  );
}
