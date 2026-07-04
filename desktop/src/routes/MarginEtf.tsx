import { useEffect, useState } from "react";
import { getPacket, postTask, type TaskCreationEnvelope } from "../api/client";
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

function etfRows(value: unknown, fallbackSource: string) {
  return rows(value).slice(0, 8).map((row, index) => ({
    序号: text(row.rank, String(index + 1)),
    ETF: text(row.name || row.etf_name || row.fund_name || row.code || row.etf_code),
    代码: text(row.code || row.etf_code || row.ts_code, ""),
    分组: text(row.bucket || row.theme || row.category),
    状态: text(row.status_label || row.state || row.action_state, "观察"),
    理由: text(row.reason || row.evidence_chain_summary || row.risk_note, "等本地快照补充"),
    来源: text(row.source, fallbackSource),
    边界: "不是买入或加融资指令"
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
        <TaskLaunchReceipt receipt={taskReceipt} />
        <TaskStatusPanel taskId={taskId} onSuccess={refresh} />
        <p className="risk-note">{boundary}</p>
      </PacketCard>

      <PacketCard title="ETF 候选分组" subtitle="推荐、观察、回避和排除分开看" status={noEtfRows ? "waiting" : "ready"}>
        <DataLineageTable rows={allVisibleEtfRows} />
        <p className="risk-note">推荐只表示优先复核；观察等待触发条件；回避/排除不能拿来追高。所有 ETF 行都不是买入、加仓或加融资指令。</p>
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
