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

const DATA_CAPABILITY_HREF = "#dataCapability";

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
  const ordinaryPlainConclusion = noEtfRows
    ? "还没有可读 ETF 候选；先看融资现金线，保持观察，不新增融资。"
    : `当前有 ${allVisibleEtfRows.length} 行 ETF 候选；${marginDecision}，先看流动性、重叠和现金线。`;
  const ordinaryPlainGap = noEtfRows
    ? "缺少 ETF 候选行；本地刷新只会回放已有快照，不会自动补外部数据。"
    : marginStatus === "ready"
      ? "仍要人工复核重叠、流动性和现金线；候选不是买入或加融资指令。"
      : "融资状态还没回放完整；不要把缺失当作可加杠杆。";
  const ordinaryPlainNow = noEtfRows
    ? "先看融资现金线；需要更新时点刷新本地回放或重建本地包。"
    : "先看 ETF 候选分组，再看融资现金线和风险提示；换票回下一票雷达。";
  const ordinaryPlainSafety = "ETF 候选只供研究，不是买入、加仓、加融资或下单指令。";
  const ordinaryPlainItems: MetricItem[] = [
    {
      label: "一句话",
      value: ordinaryPlainConclusion,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "缺口",
      value: ordinaryPlainGap,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "现在做什么",
      value: ordinaryPlainNow,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "安全说明",
      value: ordinaryPlainSafety,
      tone: "good"
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
    ? "打开 app 能看到 ETF/融资的降级等待态：先看本地快照、融资现金线和刷新本地回放入口，不新增融资。"
    : `打开 app 能看到 ${allVisibleEtfRows.length} 行 ETF 候选、融资现金线和风险提示；${marginDecision}。`;
  const marginEtfAppVisibleNowItems: MetricItem[] = [
    {
      label: "打开可见",
      value: marginEtfAppVisibleNowSentence,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "ETF 候选",
      value: noEtfRows
        ? "暂无候选；显示 degraded/等待态"
        : `推荐 ${recommendedEtfs.length} / 观察 ${watchEtfs.length} / 回避 ${avoidEtfs.length} / 排除 ${excludedEtfs.length}`,
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "融资现金线",
      value: `当前 ${percent(currentMarginRatio)} / 建议 ${percent(recommendedMarginRatio)} / 现金缓冲 ${percent(recommendedCashRatio)}`,
      tone: recommendedCashRatio ? "good" : "warn"
    },
    {
      label: "来源层",
      value: `${source} / command_center_margin_packet / bootstrap status`,
      tone: dataStatus === "ready" || dataStatus === "cached" ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: "ETF/融资缺口去数据能力页复核 Tushare、权限、空窗口和本地 packet 状态",
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "明确降级",
      value: noEtfRows ? ordinaryMissingEvidence : "候选已进入本地回放；仍需人工复核流动性、重叠和现金线",
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "下一步入口",
      value: noEtfRows ? "刷新本地回放或回下一票雷达换标的" : "先看候选分组，再看风险护栏和下一票雷达",
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "安全边界",
      value: "页面打开和本地链接只读；不自动创建任务、不调用 Tushare/DeepSeek/GitHub、不交易、不加融资",
      tone: "good"
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
        ? "暂无可读候选；只显示等待/降级"
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
      边界: "链接只切换本地页面，不创建任务、不交易、不改策略"
    }
  ];
  const marginEtfCashLineSentence = allowNewMargin
    ? "融资现金线显示仍要现金优先；即便允许小额，也必须等触发条件和数据证据齐备。"
    : "融资现金线当前结论是不新增融资；ETF 强弱只能作为研究参考，不能当加杠杆许可。";
  const marginEtfCashLineItems: MetricItem[] = [
    {
      label: "当前融资",
      value: percent(currentMarginRatio),
      tone: currentMarginRatio ? "warn" : "neutral"
    },
    {
      label: "建议融资",
      value: percent(recommendedMarginRatio),
      tone: allowNewMargin ? "warn" : "good"
    },
    {
      label: "现金缓冲",
      value: percent(recommendedCashRatio),
      tone: recommendedCashRatio ? "good" : "warn"
    },
    {
      label: "读法",
      value: marginEtfCashLineSentence,
      tone: allowNewMargin ? "warn" : "good"
    },
    {
      label: "缺口",
      value: ordinaryMissingEvidence,
      tone: noEtfRows || marginStatus !== "ready" ? "warn" : "good"
    },
    {
      label: "禁令",
      value: "融资比例不是加杠杆许可；ETF 候选不是买入或加融资指令",
      tone: "good"
    }
  ];
  const marginEtfCashLineRows = [
    {
      读法: "1. 当前融资",
      当前状态: percent(currentMarginRatio),
      用户下一步: "先确认当前融资压力，再看是否需要降低风险敞口。",
      边界: "当前比例只读本地 packet，不生成调仓或融资动作。"
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
      边界: "本地链接只切换页面，不创建 task、不调用 Tushare/DeepSeek/GitHub、不交易。"
    }
  ];
  const marginEtfRiskCardRows = [
    {
      复核项: "1. ETF 候选",
      当前状态: noEtfRows ? "暂无候选，等待本地快照或降级回放" : `${allVisibleEtfRows.length} 行候选可读`,
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
      边界: "本地链接只切换页面，不创建任务、不交易、不改策略。"
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
  const marginEtfCandidateReadingSummary = noEtfRows
    ? "暂无 ETF 候选行；先看融资现金线和缺口，不把缺数据当成低风险。"
    : `当前 ${allVisibleEtfRows.length} 行 ETF 候选先按状态和理由阅读，再核对流动性、重叠和现金/杠杆。`;
  const marginEtfCandidateReadingItems: MetricItem[] = [
    {
      label: "逐行读法",
      value: noEtfRows ? "没有候选行时先保持观察" : "先看状态和理由，再看三项风险核对",
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "状态含义",
      value: "推荐=优先复核；观察=等触发；回避/排除=不要追高",
      tone: "good"
    },
    {
      label: "风险核对",
      value: "流动性、同类重叠、现金/杠杆必须一起看",
      tone: "good"
    },
    {
      label: "缺口处理",
      value: noEtfRows ? ordinaryMissingEvidence : "缺字段按保守处理，不自动补调外部数据",
      tone: noEtfRows ? "warn" : "good"
    },
    {
      label: "边界",
      value: "ETF 行只是风险预算参考，不是买入、加仓、加融资或下单指令",
      tone: "good"
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
          怎么看: "先看融资现金线、降级原因和本地回放按钮",
          来源: source,
          风险核对: ordinaryMissingEvidence,
          边界: "缺数据时保持观察，不新增融资、不追高、不下单"
        }
      ];
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
        <div aria-label="margin etf ordinary plain conclusion">
          <h3>普通结论</h3>
          <p className="ordinary-status-note" aria-label="margin etf ordinary plain conclusion sentence" aria-live="polite">{ordinaryPlainConclusion}</p>
          <MetricGrid items={ordinaryPlainItems} />
          <p className="risk-note">普通结论只读本地 ETF/融资快照；页面打开、查看结果和切换入口都不会自动创建任务、调用外部服务或改写交易策略。</p>
        </div>
        <MetricGrid items={summaryItems} />
        <div aria-label="margin etf ordinary first screen quick read">
          <h3>现在能看什么</h3>
          <p className="ordinary-status-note" aria-label="margin etf ordinary quick read summary" aria-live="polite">{ordinaryQuickReadSummary}</p>
          <MetricGrid items={ordinaryQuickReadItems} />
          <p className="risk-note">这张速读只读本地 ETF/融资快照和本地融资状态；不会新建任务、不会调用外部数据或模型服务、不会交易或改写策略。</p>
        </div>
        <div aria-label="margin etf app visible now summary">
          <h3>打开 app 能看到什么</h3>
          <p className="ordinary-status-note" aria-label="margin etf app visible now sentence" aria-live="polite">{marginEtfAppVisibleNowSentence}</p>
          <MetricGrid items={marginEtfAppVisibleNowItems} />
          <div className="actions" aria-label="margin etf app visible now local actions">
            <a href="#candidates" title="切换到下一票雷达；换标的仍需确认按钮" aria-label="return candidate radar from margin etf visible now">换标的</a>
            <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf visible now">看风险护栏</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核 Tushare、权限、空窗口和本地 packet 状态" aria-label="open data capability from margin etf visible now">看数据能力</a>
            <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf visible now">今日作战台</a>
          </div>
          <p className="risk-note">这个条带只回答普通用户打开页面能看到什么：ETF 候选、融资现金线、来源层、降级原因和下一步入口；普通链接只切换本地页面，不创建任务、不调用 Tushare/DeepSeek/GitHub、不交易、不加融资、不改 strategy action。</p>
        </div>
        <div aria-label="margin etf candidate radar risk budget bridge">
          <h3>从候选页过来怎么看</h3>
          <p className="ordinary-status-note" aria-label="margin etf candidate bridge sentence" aria-live="polite">{marginEtfCandidateBridgeSentence}</p>
          <MetricGrid items={marginEtfCandidateBridgeItems} />
          <div className="actions" aria-label="margin etf candidate bridge local actions">
            <a href="#candidates" title="切换到下一票雷达；候选不是买入指令" aria-label="return candidate radar from margin etf bridge">回下一票雷达</a>
            <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf bridge">看风险护栏</a>
            <a href="#home" title="回今日作战台；只切换本地页面" aria-label="open home from margin etf bridge">今日作战台</a>
          </div>
          <details className="developer-audit-details" aria-label="margin etf candidate bridge rows">
            <summary>查看承接顺序</summary>
            <p className="risk-note">承接顺序只说明候选页、ETF/融资和风险护栏怎么读；不读取外部数据，不创建任务，不生成交易动作。</p>
            <DataLineageTable rows={marginEtfCandidateBridgeRows} />
          </details>
          <p className="risk-note">这张承接卡只读本地 ETF/融资快照；普通链接只切换本地页面，不刷新外部数据、不创建任务、不交易、不改策略。</p>
        </div>
        <div aria-label="margin etf cash line quick read">
          <h3>融资现金线怎么读</h3>
          <p className="ordinary-status-note" aria-label="margin etf cash line sentence" aria-live="polite">{marginEtfCashLineSentence}</p>
          <MetricGrid items={marginEtfCashLineItems} />
          <div className="actions" aria-label="margin etf cash line local actions">
            <a href="#candidates" title="切换到下一票雷达；候选不是买入指令" aria-label="return candidate radar from margin etf cash line">换标的</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核 Tushare、权限、空窗口和本地 packet 状态" aria-label="open data capability from margin etf cash line">数据能力</a>
            <a href="#risk" title="切换到风险护栏；只读本地缓存" aria-label="open risk guardrails from margin etf cash line">风险护栏</a>
          </div>
          <details className="developer-audit-details" aria-label="margin etf cash line rows">
            <summary>查看现金线读法</summary>
            <p className="risk-note">现金线读法只整理本地融资比例、建议比例、现金缓冲和缺口；不会刷新外部数据、不创建任务、不交易、不改策略。</p>
            <DataLineageTable rows={marginEtfCashLineRows} />
          </details>
          <p className="risk-note">融资现金线只用于风险预算：缺数据按保守处理；ETF 强弱不能变成买入、加仓、加融资或下单指令。</p>
        </div>
        <div aria-label="margin etf ordinary risk card">
          <h3>ETF / 融资风险卡</h3>
          <p className="ordinary-status-note" aria-label="margin etf ordinary risk card summary" aria-live="polite">{marginEtfRiskCardStatus}</p>
          <MetricGrid items={marginEtfRiskCardItems} />
          <details className="developer-audit-details" aria-label="margin etf ordinary risk card rows">
            <summary>风险复核顺序</summary>
            <p className="risk-note">这张明细只整理本地 ETF 候选、融资现金线和缺口；不读取外部数据，不创建任务，不把候选变成交易动作。</p>
            <DataLineageTable rows={marginEtfRiskCardRows} />
          </details>
          <p className="risk-note">风险卡只读本地 ETF/融资快照；ETF 候选不是买入指令，融资比例不是加杠杆许可，缺数据时按保守处理。</p>
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
        <div aria-label="margin etf candidate row reading guide">
          <h3>每行怎么读</h3>
          <p className="ordinary-status-note" aria-label="margin etf candidate row reading summary" aria-live="polite">{marginEtfCandidateReadingSummary}</p>
          <MetricGrid items={marginEtfCandidateReadingItems} />
          <details className="developer-audit-details" aria-label="margin etf candidate row reading rows">
            <summary>查看逐行读法</summary>
            <p className="risk-note">逐行读法只重排本地候选行的状态、理由、来源、流动性、重叠和现金/杠杆；不刷新外部数据、不创建任务、不交易。</p>
            <DataLineageTable rows={marginEtfCandidateReadingRows} />
          </details>
          <p className="risk-note">读法卡只帮助普通用户看懂已有 ETF 行；推荐不是买入，观察不是加仓，回避/排除不是反向交易信号。</p>
        </div>
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
