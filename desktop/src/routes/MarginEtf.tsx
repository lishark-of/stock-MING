import { useEffect, useState } from "react";
import { getBootstrapStatus, getPacket, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import PageStateBanner from "../components/PageStateBanner";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function text(value: unknown, fallback = "--") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function percent(value: unknown) {
  if (value === undefined || value === null || value === "") return "待验证";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return `${numeric % 1 === 0 ? numeric.toFixed(0) : numeric.toFixed(1)}%`;
  return text(value);
}

const runtimeModeLabels: Record<string, string> = {
  cache_only: "cache_only（只读缓存，不外联）",
  manual: "manual（仅按钮任务）",
  live_light: "live_light（轻量 task 口径，页面渲染仍不外联）",
  live_full: "live_full（预留关闭）"
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

export default function MarginEtf() {
  const [etfPacket, setEtfPacket] = useState<Record<string, unknown>>({});
  const [marginPacket, setMarginPacket] = useState<Record<string, unknown>>({});
  const [callLedger, setCallLedger] = useState<Array<Record<string, unknown>>>([]);
  const [warnings, setWarnings] = useState<Array<string>>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [taskSubmitting, setTaskSubmitting] = useState(false);
  const [taskError, setTaskError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = () => {
    setLoading(true);
    setError("");
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
  const status = text(etfPacket.status, loading ? "loading" : "waiting");
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
  const marginStatus = text(marginPacket.status ?? marginPacket.capability_state, "waiting");
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
    ? "等待本地 packet 读取完成后再创建任务"
    : error
      ? "本地 packet 读取异常；先恢复 FastAPI/cache 连接"
      : "";
  const taskDegradedReason = noEtfRows
    ? "当前没有 ETF 候选；任务只生成 degraded 本地回放收据，不会自动外联补数据。"
    : "";
  const boundary =
    "页面打开只读本地 packet；不会自动全量发现 ETF，不调用 Tushare/DeepSeek/GitHub，不下单，不把 ETF 候选写成买入或加融资指令。";
  const ordinaryQuickReadSummary = noEtfRows
    ? "当前没有可读 ETF 候选：先看本地快照状态和融资现金线，必要时只刷新本地回放。"
    : `当前可读 ${allVisibleEtfRows.length} 行 ETF 候选：先看来源、理由、流动性、重叠和现金/杠杆，再决定是否继续研究。`;
  const ordinaryMissingEvidence = noEtfRows
    ? "缺 ETF 候选行；本地刷新只生成降级回执，不自动补外部数据。"
    : marginStatus === "ready"
      ? "继续人工复核重叠、流动性和现金线；候选仍不是买入指令。"
      : "融资状态仍待本地包回放；不要把缺失数据当作可加杠杆。";
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
      ? `本地刷新已返回降级结果：${localRefreshDegradedReason}；不会自动补外部数据。`
      : `本地刷新已返回：${localRefreshRowCount} 行 ETF 候选参与回放；继续看候选分组和融资现金线。`
    : taskError
      ? `本地刷新失败：${taskError}`
      : "点击刷新/重建本地包后，这里会显示回执、降级原因、行数和安全说明。";
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
      label: "降级原因",
      value: localRefreshDegradedReason || (taskReceipt ? "未降级" : "点击后显示"),
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
      label: "缓存渲染层",
      value: `GET packet + bootstrap status 只读；runtime packet ${bootstrapPacketReady ? "可读" : "等待回放"}；页面打开、React render 和本地链接不创建 task`,
      tone: bootstrapPacketReady ? "good" : "warn"
    },
    {
      label: "按钮任务层",
      value: `${runtimeModeLabel(runtimeMode)}；刷新/重建本地包只创建 local_packet_replay POST task，不调用 provider/model`,
      tone: runtimeMode === "cache_only" ? "good" : "warn"
    },
    {
      label: "数据证据层",
      value: `${dataStatus} / ${marginStatus}；缺 ETF 或融资数据只显示 degraded，不当作无风险，也不自动补调 Tushare`,
      tone: dataStatus === "ready" || dataStatus === "cached" ? "good" : "warn"
    },
    {
      label: "旧入口退场层",
      value: "本页是 ETF/leverage 普通替代纵切；不打开 Streamlit，不移除 fallback，不把本地 packet 回放当 LTG-10 strict closeout",
      tone: "warn"
    },
    {
      label: "交易隔离层",
      value: "ETF 候选和融资比例只供研究复核；不接 broker、不创建 order endpoint、不下单、不改 strategy action",
      tone: "good"
    }
  ];
  const riskRows = [
    ...textRows(etfPacket.risk_notes, "risk_notes"),
    ...textRows(etfPacket.watch_not_chase, "watch_not_chase"),
    ...textRows(etfPacket.margin_risk_notice, "margin_risk_notice"),
    ...textRows(etfPacket.decision_guardrail, "decision_guardrail")
  ].slice(0, 12);
  const detailItems: MetricItem[] = [
    { label: "packet", value: text(etfPacket.packet_key, "command_center_etf_packet") },
    { label: "角色", value: text(etfPacket.packet_role, "ETF/融资配置证据") },
    { label: "验证", value: text(etfPacket.verification_status, "待验证"), tone: text(etfPacket.verification_status).includes("通过") ? "good" : "warn" },
    { label: "融资融券", value: marginStatus, tone: marginStatus === "ready" ? "good" : "warn" },
    { label: "来源", value: source },
    { label: "更新", value: text(etfPacket.updated_at, "暂无本地更新时间") }
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>ETF / 融资</h1>
          <p>先看 ETF 候选、融资现金线、风险提示和下一步。</p>
        </div>
        <StatusBadge label={status} tone={status === "ready" || status === "partial" ? "good" : "warn"} />
      </div>

      <PageStateBanner
        loading={loading}
        error={error}
        empty={!loading && !error && !Object.keys(etfPacket).length && !Object.keys(marginPacket).length}
        emptyTitle="暂无 ETF/融资本地快照"
        emptyDetail="本页只读取本地 packet；不会在页面打开时自动发现 ETF、拉行情或调用模型。"
      />

      <PacketCard title="ETF / 融资操作台" subtitle="普通用户先看这里" status={status}>
        <MetricGrid items={summaryItems} />
        <div aria-label="margin etf ordinary first screen quick read">
          <h3>现在能看什么</h3>
          <p className="ordinary-status-note" aria-label="margin etf ordinary quick read summary" aria-live="polite">{ordinaryQuickReadSummary}</p>
          <MetricGrid items={ordinaryQuickReadItems} />
          <p className="risk-note">这张速读只读本地 ETF/融资快照和本地融资状态；不会新建任务、不会调用外部数据或模型服务、不会交易或改写策略。</p>
        </div>
        <div aria-label="margin etf mode layered live light boundary">
          <h3>运行模式分层</h3>
          <p className="ordinary-status-note">把本地 packet、按钮任务、数据证据、旧入口退场和交易隔离分开看；live_light 也只能是可审计 task，不是页面渲染外联。</p>
          <MetricGrid items={modeLayerItems} />
        </div>
        <p className="ordinary-status-note">{text(etfPacket.evidence_summary, text(etfPacket.summary, "暂无 ETF/融资快照；先保留观察，不新增融资。"))}</p>
        <div className="actions" aria-label="margin etf primary actions">
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            title="只重新读取本地 packet；不创建 task、不调用 provider/model"
            aria-label="refresh margin etf local packets"
          >刷新本地回放</button>
          <button
            type="button"
            onClick={launchLocalRefreshTask}
            disabled={Boolean(taskDisabledReason) || taskSubmitting}
            title={taskDisabledReason || "创建本地 ETF/融资 packet 回放任务；不调用 provider/model"}
            aria-label="create margin etf local refresh task"
          >{taskSubmitting ? "创建中" : "刷新/重建本地包"}</button>
          <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf">今日作战台</a>
          <a href="#candidates" title="切换到下一票雷达；候选不是买入指令" aria-label="open candidate radar from margin etf">下一票雷达</a>
          <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf">风险护栏</a>
        </div>
        {taskDisabledReason && <p className="risk-note">任务暂不可用：{taskDisabledReason}</p>}
        {taskDegradedReason && <p className="risk-note">{taskDegradedReason}</p>}
        {taskError && <p className="risk-note">{taskError}</p>}
        {(taskReceipt || taskSubmitting || taskError || taskId) ? (
          <div aria-label="margin etf local refresh result quick read">
            <h3>刷新后结果</h3>
            <p className="ordinary-status-note" aria-label="margin etf local refresh result summary" aria-live="polite">{localRefreshReadableSummary}</p>
            <MetricGrid items={localRefreshResultItems} />
            <p className="risk-note">这张结果摘要只读按钮返回的本地回执和本地审计记录；缺 ETF 或融资包时只显示降级原因，不会补外部数据、调用模型、交易或改写策略。</p>
          </div>
        ) : null}
        <TaskLaunchReceipt receipt={taskReceipt} />
        <TaskStatusPanel taskId={taskId} onSuccess={refresh} />
        <p className="risk-note">{boundary}</p>
      </PacketCard>

      <PacketCard title="ETF 候选分组" subtitle="推荐、观察、回避和排除分开看" status={noEtfRows ? "waiting" : "ready"}>
        <DataLineageTable rows={allVisibleEtfRows} />
        <p className="risk-note">每行先看来源、状态、理由、流动性、同类重叠、融资现金线（现金/杠杆）和边界。推荐只表示优先复核；观察等待触发条件；回避/排除不能拿来追高。所有 ETF 行都不是买入、加仓或加融资指令。</p>
      </PacketCard>

      <PacketCard title="融资现金线" subtitle="先决定能不能新增风险，再看 ETF 强弱" status={allowNewMargin ? "warn" : "safe"}>
        <MetricGrid items={detailItems} />
        <DataLineageTable rows={riskRows} />
      </PacketCard>

      <details className="developer-audit-details" aria-label="margin etf audit details">
        <summary>研究辅助 / 审计详情</summary>
        <p className="risk-note">这里仅用于排查本地 packet 来源、warning 和 GET ledger；不展示 token/key，不触发外部刷新。</p>
        <DataLineageTable rows={warnings.map((warning, index) => ({ 序号: index + 1, warning }))} />
        <DataLineageTable rows={callLedger} />
      </details>
    </>
  );
}
