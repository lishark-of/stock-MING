import { useEffect, useState } from "react";
import { getModelStrategyCache, postDeepseekProviderBenchmarkExecutionRequest, postDeepseekProviderBenchmarkScopeTicket, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function listText(value: unknown, fallback: string[]): string {
  const items = Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : fallback;
  return items.join(" / ");
}

export default function ModelStrategy() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [scopeTicketSubmitting, setScopeTicketSubmitting] = useState(false);
  const [scopeTicketError, setScopeTicketError] = useState("");
  const [executionRequestReceipt, setExecutionRequestReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [executionRequestSubmitting, setExecutionRequestSubmitting] = useState(false);
  const [executionRequestError, setExecutionRequestError] = useState("");

  const refreshModelStrategyCache = () => {
    void getModelStrategyCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  };

  useEffect(() => {
    refreshModelStrategyCache();
  }, []);

  const launchScopeTicket = () => {
    if (scopeTicketSubmitting) return;
    setScopeTicketSubmitting(true);
    setScopeTicketError("");
    void postDeepseekProviderBenchmarkScopeTicket({
      approved_by_user: true,
      sample_count: 40,
      response_format: "json_schema",
      max_retry_per_sample: 2,
      requested_by: "model_strategy_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (!res.ok) {
        setScopeTicketError(res.error ?? "deepseek_scope_ticket_task_failed");
      }
      refreshModelStrategyCache();
    }).catch(() => {
      setTaskReceipt(null);
      setScopeTicketError("deepseek_scope_ticket_submit_exception");
    }).finally(() => setScopeTicketSubmitting(false));
  };

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const groups = (cache.purpose_groups as Record<string, unknown> | undefined) ?? {};
  const governedExecutor = (cache.governed_executor as Record<string, unknown> | undefined) ?? {};
  const governedExecutorOneScreenSummary =
    (cache.ordinary_one_screen_summary as Record<string, unknown> | undefined) ??
    (governedExecutor.ordinary_one_screen_summary as Record<string, unknown> | undefined) ??
    {};
  const governedExecutorScopeHash = String(governedExecutor.provider_benchmark_scope_hash ?? "");
  const governedExecutorScopeHashReady =
    governedExecutor.provider_benchmark_scope_ticket_ready === true &&
    governedExecutor.provider_benchmark_scope_hash_safe_to_bind === true &&
    governedExecutorScopeHash.length === 64;
  const governedExecutorRealCallGateRows = rows(governedExecutor.real_call_gate_rows);
  const governedExecutorRealCallAllowed = governedExecutor.real_call_allowed_now === true;
  const governedExecutorRealCallBlockers = Array.isArray(governedExecutor.real_call_blockers)
    ? governedExecutor.real_call_blockers.map((item) => String(item)).filter(Boolean)
    : [];
  const launchExecutionRequest = () => {
    if (executionRequestSubmitting) return;
    if (!governedExecutorScopeHashReady) {
      setExecutionRequestError("deepseek_execution_request_scope_hash_missing");
      return;
    }
    setExecutionRequestSubmitting(true);
    setExecutionRequestError("");
    void postDeepseekProviderBenchmarkExecutionRequest({
      approved_by_user: true,
      confirm_execution_request: true,
      benchmark_scope_hash: governedExecutorScopeHash,
      requested_by: "model_strategy_page"
    }).then((res) => {
      setExecutionRequestReceipt(res);
      if (!res.ok) {
        setExecutionRequestError(res.error ?? "deepseek_execution_request_task_failed");
      }
      refreshModelStrategyCache();
    }).catch(() => {
      setExecutionRequestReceipt(null);
      setExecutionRequestError("deepseek_execution_request_submit_exception");
    }).finally(() => setExecutionRequestSubmitting(false));
  };
  const modelRows = rows(cache.model_rows);
  const modelSafetyRows = [
    {
      check: "does_not_hardcode_model",
      passed_count: modelRows.filter((row) => row.does_not_hardcode_model === true).length,
      total_count: modelRows.length,
      status: modelRows.length && modelRows.every((row) => row.does_not_hardcode_model === true) ? "passed" : "check"
    },
    {
      check: "contains_secret",
      passed_count: modelRows.filter((row) => row.contains_secret === false).length,
      total_count: modelRows.length,
      status: modelRows.length && modelRows.every((row) => row.contains_secret === false) ? "passed" : "check"
    },
    {
      check: "external_call_on_cache_read",
      passed_count: modelRows.filter((row) => row.external_call_on_cache_read === false).length,
      total_count: modelRows.length,
      status: modelRows.length && modelRows.every((row) => row.external_call_on_cache_read === false) ? "passed" : "check"
    }
  ];
  const payloadCallLedger = rows(cache.call_ledger);
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const executionRequestPayloadReceipt = (
    executionRequestReceipt?.data?.task?.payload_safe?.deepseek_provider_benchmark_execution_request_receipt as Record<string, unknown> | undefined
  ) ?? {};
  const governedExecutorStandaloneBoundary =
    "DeepSeek 补证是单独 P5 executor；不阻塞 P1 Tushare-first、P2 小数据写入或 P3 基础图谱，也不从本页触发真实模型调用。";
  const governedExecutorAllowedOutputFields = listText(
    governedExecutor.ordinary_allowed_output_fields,
    ["summary", "support_notes", "suppress_notes", "conflict_notes", "missing_data_notes", "discipline_notes"]
  );
  const governedExecutorForbiddenOutputTargets = listText(
    governedExecutor.ordinary_forbidden_output_targets,
    ["price", "holding", "factor", "operation_zones", "strategy_action", "trade_order"]
  );
  const governedExecutorOrdinaryChecklistRows = [
    {
      治理项: "执行门控",
      当前状态: governedExecutor.scope_ticket_ready === true || governedExecutor.provider_benchmark_scope_ticket_ready === true ? "scope ticket ready" : "等待 scope ticket",
      用户下一步: "先继续 Tushare-first / Factor light / Next Session；DeepSeek 单独补证",
      边界: "真实模型调用只能走 POST task + model_ledger + sanitizer / redaction / output acceptance"
    },
    {
      治理项: "输出范围",
      当前状态: governedExecutor.sanitizer_ready === true && governedExecutor.redaction_review_ready === true ? "sanitizer / redaction ready" : "等待 sanitizer / redaction review",
      用户下一步: "只看已有证据解释，不把模型当数据源",
      边界: "DeepSeek 不覆盖价格、持仓、factor、operation_zones 或 strategy action"
    },
    {
      治理项: "不阻塞基础路径",
      当前状态: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? "Tushare-first / Factor light / Next Session 可先走" : "待确认非阻塞边界",
      用户下一步: "继续确认按钮链路和本地 cache 回放",
      边界: "DeepSeek pending 不阻塞 P1/P2/P3；本页 GET cache 不调用模型"
    }
  ];
  const governedExecutorOutputContractRows = [
    {
      准入项: "允许输出字段",
      当前状态: governedExecutorAllowedOutputFields,
      用户下一步: "只读安全解释摘要；不看 raw prompt / raw output。",
      边界: "字段白名单以外内容必须丢弃或继续等待治理。"
    },
    {
      准入项: "禁止覆盖目标",
      当前状态: governedExecutorForbiddenOutputTargets,
      用户下一步: "价格、持仓、因子、operation_zones 和 action 仍以本地数据链为准。",
      边界: "DeepSeek 不写数值源、不改操作区、不生成交易动作。"
    },
    {
      准入项: "只读准入契约",
      当前状态: governedExecutor.ordinary_output_contract_is_cache_only === false ? "异常：需要审计" : "cache-only / no task / no model call",
      用户下一步: "继续 P1/P2/P3；P5 单独补 governed executor。",
      边界: "本表来自 GET cache，不创建 POST task，不调用 DeepSeek。"
    }
  ];
  const governedExecutorNonblockingRows = [
    {
      普通路径: "Tushare-first 数据链",
      当前状态: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "可先走：DeepSeek pending 不阻塞确认按钮后的 Tushare-first" : "待确认非阻塞边界",
      用户动作: "继续看下一票雷达确认任务、Tushare call_ledger 和 cache 回放",
      边界: "DeepSeek 不作为数据源；缺 model_ledger 不阻断 Tushare-first POST task"
    },
    {
      普通路径: "Factor light 量化推演",
      当前状态: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "可先读：支持/压制来自本地 Factor cache" : "待确认非阻塞边界",
      用户动作: "先按支持/压制、冲突和缺失项复核本地结果",
      边界: "DeepSeek 不覆盖价格、因子、持仓或 strategy action"
    },
    {
      普通路径: "Next Session 基础图谱",
      当前状态: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "可先读：图谱路径、参考线和操作区不等模型" : "待确认非阻塞边界",
      用户动作: "继续看次日图谱本地 cache、路径和 operation_zones",
      边界: "DeepSeek 不改 operation_zones；图谱不是买卖或下单指令"
    }
  ];
  const governedExecutorOrdinaryQuickReadRows = [
    {
      速读项: "现在先做",
      当前状态: "继续 P1 Tushare-first、P2 cache/ledger/packet 回放、P3 基础图谱。",
      用户下一步: "不用等待模型；先看确认任务、支持/压制和次日图谱。",
      边界: "这些入口只读本地 cache 或按钮任务状态，不从本页调用 DeepSeek。"
    },
    {
      速读项: "DeepSeek 等什么",
      当前状态: String(governedExecutor.ordinary_required_before_real_call ?? "等待 model_ledger / sanitizer / redaction review / cost accounting / output acceptance"),
      用户下一步: "把模型补证当单独验收，不拿 pending 状态阻断基础投研。",
      边界: "缺 model_ledger 不能当真实模型证据，也不能升级 production evidence。"
    },
    {
      速读项: "真实调用闸门",
      当前状态: governedExecutorRealCallAllowed ? "已放行" : `未放行：${governedExecutorRealCallBlockers.join(" / ") || "等待 governed executor evidence"}`,
      用户下一步: "继续按本地 scope ticket / execution-request / model_ledger / sanitizer 顺序补证。",
      边界: "闸门状态只读来自 GET cache；不会从页面打开、React render 或 GET cache 调用 DeepSeek。"
    },
    {
      速读项: "不会碰什么",
      当前状态: "不覆盖价格、持仓、因子、operation_zones 或 strategy action。",
      用户下一步: "模型解释只看已有证据的解释状态，不替代数据源。",
      边界: "DeepSeek 文本不是买卖指令，不生成交易动作。"
    },
    {
      速读项: "何时再补",
      当前状态: governedExecutor.model_ledger_ready === true || governedExecutor.model_ledger_evidence_done === true ? "model_ledger 已就绪，可进入后续治理验收" : "model_ledger pending；继续本地回放",
      用户下一步: "等 governed executor 完成后，再单独跑受控模型补证。",
      边界: "真实调用只能走受控 POST task / executor，不从 GET cache 或 React render 触发。"
    }
  ];
  const governedExecutorScopeTicketReadbackRows = [
    {
      回读项: "scope ticket 状态",
      当前状态: String(governedExecutor.provider_benchmark_scope_ticket_status ?? "deepseek_provider_benchmark_scope_ticket_missing"),
      用户下一步: governedExecutor.provider_benchmark_scope_ticket_ready === true ? "保留本地 scope ticket，继续补 model_ledger / sanitizer / output acceptance" : "需要时点击下方按钮生成本地 scope ticket",
      边界: "GET model strategy cache 只读回放已存在的 factor quant packet，不初始化 scope ticket。"
    },
    {
      回读项: "scope hash",
      当前状态: String(governedExecutor.provider_benchmark_scope_hash_short ?? "pending"),
      用户下一步: "后续真实 provider benchmark 必须绑定这个本地 scope hash。",
      边界: "hash 是 scope 绑定证据，不是 provider benchmark 或模型正确性证据。"
    },
    {
      回读项: "model call 状态",
      当前状态: String(governedExecutor.provider_benchmark_scope_ticket_model_call_status ?? "not_called"),
      用户下一步: "真实 DeepSeek 调用继续等待受控 executor。",
      边界: "scope ticket 和 GET cache 都不调用 DeepSeek。"
    },
    {
      回读项: "readback 边界",
      当前状态: governedExecutor.provider_benchmark_scope_ticket_cache_read_initializes_ticket === true ? "异常：需要审计" : "cache read 不初始化票据",
      用户下一步: "继续 P1/P2/P3；P5 只按按钮门控推进。",
      边界: "不创建 task、不读取 token/key、不阻塞 Tushare-first 或基础图谱。"
    }
  ];
  const governedExecutorExecutionRequestReadbackRows = [
    {
      回读项: "execution request 状态",
      当前状态: String(governedExecutor.provider_benchmark_execution_request_status ?? "deepseek_provider_benchmark_execution_request_missing"),
      用户下一步: governedExecutor.provider_benchmark_execution_request_ready === true ? "保留本地 execution-request ticket；真实模型调用继续等 model_ledger / sanitizer / output acceptance" : "scope ticket ready 后点击下方按钮生成本地 execution-request",
      边界: "GET model strategy cache 只读回放已存在的 execution-request；不会创建模型任务。"
    },
    {
      回读项: "scope 绑定",
      当前状态: governedExecutor.provider_benchmark_execution_request_scope_hash_matches_latest === true ? "scope hash 已绑定 latest ticket" : "等待 scope hash 绑定",
      用户下一步: "只用本地 scope digest 绑定后续 governed benchmark；不传 token/key。",
      边界: "scope hash 是安全 digest，不是 provider benchmark、model_ledger 或模型正确性证据。"
    },
    {
      回读项: "model task 状态",
      当前状态: governedExecutor.provider_benchmark_execution_request_model_task_created === true ? "异常：需要审计" : "未创建模型任务",
      用户下一步: "真实 DeepSeek benchmark 继续等待单独 governed executor。",
      边界: "execution-request ticket 不调用 DeepSeek、不写 model output、不写 model_ledger。"
    },
    {
      回读项: "readback 边界",
      当前状态: governedExecutor.provider_benchmark_execution_request_cache_read_initializes_ticket === true ? "异常：需要审计" : "cache read 不初始化 execution-request",
      用户下一步: "继续 P1/P2/P3；P5 只按按钮门控推进。",
      边界: "不创建 task、不读取 token/key、不阻塞 Tushare-first 或基础图谱。"
    }
  ];
  const governedExecutorRailState = [
    governedExecutor.scope_ticket_ready === true || governedExecutor.provider_benchmark_scope_ticket_ready === true ? "scope_ticket_ready" : "scope_ticket_pending",
    governedExecutor.provider_benchmark_execution_request_ready === true ? "execution_request_ready" : "execution_request_pending",
    governedExecutor.sanitizer_ready === true && governedExecutor.redaction_review_ready === true ? "sanitizer_redaction_ready" : "sanitizer_redaction_pending",
    governedExecutor.model_ledger_ready === true || governedExecutor.model_ledger_evidence_done === true ? "model_ledger_ready" : "model_ledger_pending",
    governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? "ordinary_paths_unblocked" : "ordinary_paths_check"
  ].join(" ");
  const governedExecutorRailSteps = [
    {
      label: "scope ticket",
      state: governedExecutor.scope_ticket_ready === true || governedExecutor.provider_benchmark_scope_ticket_ready === true ? ("done" as const) : ("waiting" as const),
      detail: String(governedExecutor.scope_ticket_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket")
    },
    {
      label: "execution request",
      state: governedExecutor.provider_benchmark_execution_request_ready === true ? ("done" as const) : governedExecutorScopeHashReady ? ("active" as const) : ("waiting" as const),
      detail: String(governedExecutor.execution_request_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-execution-request")
    },
    {
      label: "sanitizer / redaction",
      state: governedExecutor.sanitizer_ready === true && governedExecutor.redaction_review_ready === true ? ("done" as const) : ("active" as const),
      detail: "真实调用前需要 sanitizer、redaction review 和 output acceptance"
    },
    {
      label: "model ledger",
      state: governedExecutor.model_ledger_ready === true || governedExecutor.model_ledger_evidence_done === true ? ("done" as const) : ("waiting" as const),
      detail: String(governedExecutor.ordinary_required_before_real_call ?? "需要 model_ledger / cost accounting / output acceptance")
    },
    {
      label: "普通路径非阻塞",
      state: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? ("done" as const) : ("active" as const),
      detail: "Tushare-first / Factor light / Next Session 可先走"
    }
  ];
  const governedExecutorFrontSummaryItems = [
    {
      label: "当前结论",
      value: cache.deepseek_called === true ? "已记录 DeepSeek 调用；先看 model_ledger" : "当前未调用 DeepSeek；基础投研可先看",
      tone: cache.deepseek_called === true ? ("warn" as const) : ("good" as const)
    },
    {
      label: "基础路径",
      value: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true || governedExecutor.does_not_block_tushare_first_or_basic_maps === true
        ? "不阻塞：Tushare-first、股票量化推演、次日图谱可先走"
        : "待确认：先看本地回放，不把模型 pending 当阻断",
      tone: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true || governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? ("good" as const) : ("warn" as const)
    },
    {
      label: "真实调用",
      value: governedExecutorRealCallAllowed ? "已放行" : `未放行：${governedExecutorRealCallBlockers.length || governedExecutor.real_call_blocker_count || 0} 项待补`,
      tone: governedExecutorRealCallAllowed ? ("good" as const) : ("warn" as const)
    },
    {
      label: "下一步",
      value: "继续 P1 确认按钮、P2 小数据回放、P3 基础图谱；P5 模型补证单独做",
      tone: "good" as const
    },
    {
      label: "安全边界",
      value: "GET cache 只读；页面打开、React render 和本卡不会调用 DeepSeek",
      tone: "good" as const
    },
    {
      label: "凭据",
      value: cache.contains_secret === true ? "异常：需要审计" : "不展示 token/key；前端只显示安全状态",
      tone: cache.contains_secret === true ? ("bad" as const) : ("good" as const)
    }
  ];
  const governedExecutorTechnicalCounterItems = [
    { label: "mode", value: cache.mode as string | undefined },
    { label: "purposes", value: counts.purpose_count as number | undefined },
    { label: "configured", value: counts.configured_count as number | undefined },
    { label: "safe defaults", value: counts.safe_default_count as number | undefined },
    { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? ("bad" as const) : ("good" as const) },
    { label: "DeepSeek call", value: cache.deepseek_called === true ? "已调用" : "未调用", tone: cache.deepseek_called === true ? ("bad" as const) : ("good" as const) },
    { label: "governed executor", value: String(governedExecutor.status ?? "pending"), tone: governedExecutor.deepseek_called === true ? ("bad" as const) : ("warn" as const) },
    { label: "real call gate", value: governedExecutorRealCallAllowed ? "允许" : `未放行：${governedExecutorRealCallBlockers.length || governedExecutor.real_call_blocker_count || 0} 项`, tone: governedExecutorRealCallAllowed ? ("good" as const) : ("warn" as const) },
    { label: "Tushare/basic maps", value: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? "不阻塞" : "待确认", tone: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? ("good" as const) : ("warn" as const) },
    { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? ("bad" as const) : ("good" as const) },
    { label: "contains secret", value: cache.contains_secret === true ? "是" : "否", tone: cache.contains_secret === true ? ("bad" as const) : ("good" as const) },
    { label: "cache envelope ledger", value: cacheCallLedger.length },
    { label: "cache warnings", value: cacheWarnings.length }
  ];
  const governedExecutorOneScreenItems = [
    { label: "当前结论", value: String(governedExecutorOneScreenSummary.headline ?? "DeepSeek 暂不调用，基础投研可继续"), tone: governedExecutorOneScreenSummary.real_call_allowed_now === true ? ("good" as const) : ("warn" as const) },
    { label: "当前状态", value: String(governedExecutorOneScreenSummary.current_state ?? governedExecutor.ordinary_status_label ?? "等待 governed executor"), tone: "warn" as const },
    { label: "下一步", value: String(governedExecutorOneScreenSummary.next_action ?? governedExecutor.ordinary_next_allowed_action ?? "先继续 P1/P2/P3 本地回放；P5 单独补证。"), tone: "good" as const },
    { label: "真实调用", value: governedExecutorOneScreenSummary.real_call_allowed_now === true ? "已放行" : `未放行：${String(governedExecutorOneScreenSummary.real_call_blocker_count ?? governedExecutor.real_call_blocker_count ?? 0)} 项 blocker`, tone: governedExecutorOneScreenSummary.real_call_allowed_now === true ? ("good" as const) : ("warn" as const) },
    { label: "基础路径", value: String(governedExecutorOneScreenSummary.basic_research_boundary ?? "Tushare-first / Factor light / Next Session 可先走"), tone: "good" as const },
    { label: "边界", value: "cache-only 摘要；不创建 task、不调用 DeepSeek、不含 token/key、不是 production evidence", tone: "good" as const }
  ];

  return (
    <>
      <div className="page-head">
        <h1>DeepSeek 模型策略</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "warn"} />
      </div>

      <MetricGrid items={governedExecutorFrontSummaryItems} />
      <p className="risk-note" aria-label="deepseek ordinary top summary boundary">
        这张首屏摘要只读 /api/model-strategy/cache；不创建 task、不调用 DeepSeek、不读取 token/key，也不阻塞 Tushare-first、P2 小数据回放或 P3 基础图谱。
      </p>
      <details className="developer-audit-details" aria-label="deepseek model strategy top technical counters">
        <summary>模型策略计数 / cache 明细</summary>
        <MetricGrid items={governedExecutorTechnicalCounterItems} />
      </details>

      <div className="grid">
        <PacketCard title="普通用户 DeepSeek 状态" subtitle="P5 governed executor；真实模型调用单独补，不阻塞 Tushare-first 和基础图谱" status={String(governedExecutor.status ?? "pending")}>
          <p>{String(governedExecutor.ordinary_status_label ?? "DeepSeek 等 governed executor；Tushare-first 和基础图谱可先走。")}</p>
          <div aria-label="deepseek governed executor one screen summary">
            <h3>P5 一屏结论</h3>
            <MetricGrid items={governedExecutorOneScreenItems} />
            <p className="risk-note">这张一屏结论来自 GET /api/model-strategy/cache 的 ordinary_one_screen_summary；只读、不创建 task、不调用模型、不展示 token/key，也不作为 production evidence。</p>
          </div>
          <MetricGrid
            items={[
              { label: "下一步", value: String(governedExecutor.ordinary_next_allowed_action ?? "先继续 Tushare-first、Factor light 和 Next Session 本地回放；DeepSeek 单独验收。") },
              { label: "P5 单独补证", value: governedExecutorStandaloneBoundary, tone: "good" },
              { label: "必备治理", value: String(governedExecutor.ordinary_required_before_real_call ?? "需要 model_ledger / sanitizer / redaction review / cost accounting / output acceptance 全部就绪。"), tone: "warn" },
              { label: "真实调用", value: governedExecutorRealCallAllowed ? "已放行" : `未放行：${governedExecutorRealCallBlockers.length || governedExecutor.real_call_blocker_count || 0} 项 blocker`, tone: governedExecutorRealCallAllowed ? "good" : "warn" },
              { label: "非阻塞", value: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "Tushare-first / Factor light / Next Session 可先走" : "待确认", tone: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "good" : "warn" },
              { label: "阻断状态", value: String(governedExecutor.ordinary_blocking_state ?? "pending_model_ledger_not_blocking_tushare_or_basic_maps"), tone: "warn" },
              { label: "边界", value: String(governedExecutor.ordinary_nonblocking_boundary ?? "DeepSeek 只解释已有证据，不作为数据源、不生成买卖动作。"), tone: "good" }
            ]}
          />
          <p>必须先有 model_ledger、sanitizer、redaction review、cost accounting 和 output acceptance；本页 GET cache 与 React render 都不调用模型。</p>
          <p>DeepSeek 只解释已有证据，不覆盖价格、持仓、因子、operation zones 或 strategy action。</p>
          <StateClarityRail
            label="deepseek governed executor readiness status"
            state={governedExecutorRailState}
            steps={governedExecutorRailSteps}
          />
          <p className="risk-note">P5 准入状态：scope ticket / sanitizer-redaction / model ledger / 普通路径非阻塞；这条状态轨只读本地 cache，不调用 DeepSeek、不阻塞 Tushare-first 或基础图谱。</p>
          <div aria-label="deepseek governed executor ordinary quick read">
            <h3>P5 普通用户速读</h3>
            <p className="risk-note">先看现在能做什么、DeepSeek 还等什么、不会改哪些数据；这张表不展开执行路由、raw policy 或模型输出。</p>
            <DataLineageTable rows={governedExecutorOrdinaryQuickReadRows} />
          </div>
          <div aria-label="deepseek governed executor output contract">
            <h3>P5 安全输出白名单</h3>
            <p className="risk-note">{String(governedExecutor.ordinary_output_contract_label ?? "仅允许安全解释字段；禁止覆盖价格、持仓、factor、operation_zones、strategy action 或交易动作。")}</p>
            <DataLineageTable rows={governedExecutorOutputContractRows} />
          </div>
          <div aria-label="deepseek governed executor nonblocking ordinary paths">
            <h3>不阻塞基础投研路径</h3>
            <p className="risk-note">DeepSeek governed executor 未完成前，普通用户仍可先看 Tushare-first、Factor light 和 Next Session 本地回放。</p>
            <DataLineageTable rows={governedExecutorNonblockingRows} />
          </div>
          <div className="actions" aria-label="deepseek governed executor nonblocking handoff links">
            <a href="#candidates" title="回到下一票雷达；确认按钮才创建 Tushare-first task" aria-label="continue tushare first candidate radar while deepseek pending">继续下一票雷达</a>
            <a href="#factor" title="打开股票量化推演；只读 Factor cache 和本地结果" aria-label="continue factor light replay while deepseek pending">查看股票量化推演</a>
            <a href="#next" title="打开次日图谱；只读本地次日图谱结果" aria-label="continue next session map while deepseek pending">查看次日图谱</a>
          </div>
          <p className="risk-note">这些入口只切换本地页面；不会创建 DeepSeek task、不会调用模型，也不会把 pending 状态当生产验收。</p>
          <details className="developer-audit-details" aria-label="deepseek governed executor ticket and gate details">
            <summary>P5 本地票据 / 闸门审计</summary>
            <p className="risk-note">scope ticket、execution-request、真实调用闸门和本地票据按钮默认下沉；需要补证时再展开。这里仍只创建本地票据，不调用 DeepSeek、不读取 token/key、不阻塞 Tushare-first 或基础图谱。</p>
            <div aria-label="deepseek governed executor scope ticket readback">
              <h3>P5 scope ticket 回读</h3>
              <p className="risk-note">刷新后优先看这里：它只读已持久化的本地 scope ticket 状态，不从 GET cache 创建票据、不调用 DeepSeek。</p>
              <DataLineageTable rows={governedExecutorScopeTicketReadbackRows} />
            </div>
            <div aria-label="deepseek governed executor execution request readback">
              <h3>P5 execution-request 回读</h3>
              <p className="risk-note">scope ticket 之后只生成本地 execution-request ticket；它绑定 scope hash，不创建模型任务、不调用 DeepSeek。</p>
              <DataLineageTable rows={governedExecutorExecutionRequestReadbackRows} />
            </div>
            <div aria-label="deepseek governed executor real call gate">
              <h3>P5 真实调用闸门</h3>
              <p className="risk-note">真实 DeepSeek 调用必须等所有 gate 通过；当前表只读展示 blocker，不创建任务、不调用模型、不展示 token/key。</p>
              <DataLineageTable rows={governedExecutorRealCallGateRows} />
            </div>
            <div aria-label="deepseek governed executor ordinary checklist">
              <h3>P5 治理清单</h3>
              <p className="risk-note">普通用户只看能不能安全补证、是否阻塞基础路径；执行路由、scope ticket 和 raw policy 仍在详情里。</p>
              <DataLineageTable rows={governedExecutorOrdinaryChecklistRows} />
            </div>
            <div aria-label="deepseek governed executor scope ticket action">
              <h3>P5 本地 scope ticket</h3>
              <p className="risk-note">这个按钮只创建本地 provider benchmark scope ticket，写入本地任务回执；不调用 DeepSeek、不读取 token/key、不阻塞 Tushare-first 或基础图谱。</p>
              <div className="actions">
                <button onClick={launchScopeTicket} disabled={scopeTicketSubmitting}>
                  {scopeTicketSubmitting ? "生成中" : "生成 P5 本地 scope ticket"}
                </button>
              </div>
              {scopeTicketError && <p className="risk-note">{scopeTicketError}</p>}
              <MetricGrid
                items={[
                  { label: "任务", value: taskReceipt?.data?.task_id ?? "等待点击", tone: taskReceipt?.ok ? "good" : "warn" },
                  { label: "DeepSeek call", value: taskReceipt?.data?.task?.deepseek_called === true ? "已调用" : "未调用", tone: taskReceipt?.data?.task?.deepseek_called === true ? "bad" : "good" },
                  { label: "外联", value: taskReceipt?.data?.task?.external_calls_triggered === true ? "存在" : "无", tone: taskReceipt?.data?.task?.external_calls_triggered === true ? "bad" : "good" },
                  { label: "真实交易", value: taskReceipt?.data?.task?.does_not_execute_trades === false ? "可能" : "禁止", tone: taskReceipt?.data?.task?.does_not_execute_trades === false ? "bad" : "good" }
                ]}
              />
              <TaskLaunchReceipt receipt={taskReceipt} />
            </div>
            <div aria-label="deepseek governed executor execution request action">
              <h3>P5 本地 execution-request</h3>
              <p className="risk-note">这个按钮只绑定本地 scope hash 并生成 execution-request ticket；不调用 DeepSeek、不创建模型任务、不写 model_ledger，也不阻塞 Tushare-first 或基础图谱。</p>
              <div className="actions">
                <button onClick={launchExecutionRequest} disabled={executionRequestSubmitting || !governedExecutorScopeHashReady}>
                  {executionRequestSubmitting ? "生成中" : "生成 P5 本地 execution-request"}
                </button>
              </div>
              {!governedExecutorScopeHashReady && <p className="risk-note">需要先生成 P5 本地 scope ticket，才可绑定 scope hash。</p>}
              {executionRequestError && <p className="risk-note">{executionRequestError}</p>}
              <MetricGrid
                items={[
                  { label: "任务", value: executionRequestReceipt?.data?.task_id ?? "等待点击", tone: executionRequestReceipt?.ok ? "good" : "warn" },
                  { label: "DeepSeek call", value: executionRequestReceipt?.data?.task?.deepseek_called === true ? "已调用" : "未调用", tone: executionRequestReceipt?.data?.task?.deepseek_called === true ? "bad" : "good" },
                  { label: "模型任务", value: executionRequestPayloadReceipt.model_task_created === true ? "已创建" : "未创建", tone: executionRequestPayloadReceipt.model_task_created === true ? "bad" : "good" },
                  { label: "真实交易", value: executionRequestReceipt?.data?.task?.does_not_execute_trades === false ? "可能" : "禁止", tone: executionRequestReceipt?.data?.task?.does_not_execute_trades === false ? "bad" : "good" }
                ]}
              />
              <TaskLaunchReceipt receipt={executionRequestReceipt} />
            </div>
          </details>
          <details className="developer-audit-details">
            <summary>P5 执行路由详情</summary>
            <p>真实调用入口：{String(governedExecutor.execution_route ?? "POST /api/factor-quant/deepseek-explain")}；scope ticket：{String(governedExecutor.scope_ticket_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket")}；execution-request：{String(governedExecutor.execution_request_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-execution-request")}。</p>
          </details>
        </PacketCard>

        <PacketCard title="模型策略边界" subtitle="GET /api/model-strategy/cache 只读；不触发模型调用" status="cache_only">
          <p>{String(cache.summary ?? "DeepSeek 模型策略只读展示。")}</p>
          <p>模型名通过 DEEPSEEK_EXPLAIN_MODEL、DEEPSEEK_FAST_MODEL、DEEPSEEK_DEFAULT_MODEL 配置，调用点不得硬编码模型名。</p>
          <p>本页不读取凭据、不会调用 DeepSeek、不调用 Tushare/GitHub、不执行真实交易、不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="用途分组" subtitle="解释类默认走更强模型，轻量检查走 fast 模型" status="purpose_groups">
          <p>explain grade: {rows(groups.explain_grade).length ? JSON.stringify(groups.explain_grade) : String(groups.explain_grade ?? "--")}</p>
          <p>fast grade: {rows(groups.fast_grade).length ? JSON.stringify(groups.fast_grade) : String(groups.fast_grade ?? "--")}</p>
          <p>does_not_call_deepseek: {String(policy.does_not_call_deepseek ?? true)}</p>
          <p>post_task_required_for_model_call: {String(policy.post_task_required_for_model_call ?? true)}</p>
        </PacketCard>
      </div>

      <details className="developer-audit-details">
        <summary>模型策略开发 / 审计详情</summary>
        <p>普通用户先看上方 DeepSeek 状态、模型策略边界和用途分组；模型映射、安全摘要、policy、call_ledger、warnings 和 raw payload 默认收起。</p>

        <PacketCard title="用途到模型映射" subtitle="model_rows；只展示模型名和配置键名，不展示凭据" status="models">
          <DataLineageTable rows={modelRows} />
        </PacketCard>

        <PacketCard title="模型策略安全摘要" subtitle="每个 purpose 都必须声明不硬编码模型名、不含凭据、cache read 不外联" status="model_safety">
          <p>安全摘要来自 GET /api/model-strategy/cache 的 model_rows；只读、不调用 DeepSeek。</p>
          <DataLineageTable rows={modelSafetyRows} />
        </PacketCard>

        <PacketCard title="安全策略" subtitle="cache API 永不外联；DeepSeek 只能按钮门控" status="policy">
          <DataLineageTable rows={[policy]} />
        </PacketCard>

        <PacketCard title="调用血缘" subtitle="local_deepseek_model_strategy_cache；不外联" status="lineage">
          <DataLineageTable rows={payloadCallLedger} />
        </PacketCard>

        <PacketCard title="GET model strategy envelope call_ledger" subtitle="GET /api/model-strategy/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
          <DataLineageTable rows={cacheCallLedger} />
        </PacketCard>

        <PacketCard title="GET model strategy envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
          <DataLineageTable rows={warningRows} />
        </PacketCard>

        <PacketCard title="原始 model strategy payload" subtitle="调试用 JSON；不含凭据" status="safe">
          <JsonDetails title="model strategy raw" data={cache} />
        </PacketCard>
      </details>
    </>
  );
}
