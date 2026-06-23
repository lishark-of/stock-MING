import { useEffect, useState } from "react";
import { getModelStrategyCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function ModelStrategy() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getModelStrategyCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const groups = (cache.purpose_groups as Record<string, unknown> | undefined) ?? {};
  const governedExecutor = (cache.governed_executor as Record<string, unknown> | undefined) ?? {};
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
  const governedExecutorStandaloneBoundary =
    "DeepSeek 补证是单独 P5 executor；不阻塞 P1 Tushare-first、P2 小数据写入或 P3 基础图谱，也不从本页触发真实模型调用。";
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
  const governedExecutorRailState = [
    governedExecutor.scope_ticket_ready === true || governedExecutor.provider_benchmark_scope_ticket_ready === true ? "scope_ticket_ready" : "scope_ticket_pending",
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

  return (
    <>
      <div className="page-head">
        <h1>DeepSeek 模型策略</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "warn"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "purposes", value: counts.purpose_count as number | undefined },
          { label: "configured", value: counts.configured_count as number | undefined },
          { label: "safe defaults", value: counts.safe_default_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "DeepSeek call", value: cache.deepseek_called === true ? "已调用" : "未调用", tone: cache.deepseek_called === true ? "bad" : "good" },
          { label: "governed executor", value: String(governedExecutor.status ?? "pending"), tone: governedExecutor.deepseek_called === true ? "bad" : "warn" },
          { label: "Tushare/basic maps", value: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? "不阻塞" : "待确认", tone: governedExecutor.does_not_block_tushare_first_or_basic_maps === true ? "good" : "warn" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "contains secret", value: cache.contains_secret === true ? "是" : "否", tone: cache.contains_secret === true ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="普通用户 DeepSeek 状态" subtitle="P5 governed executor；真实模型调用单独补，不阻塞 Tushare-first 和基础图谱" status={String(governedExecutor.status ?? "pending")}>
          <p>{String(governedExecutor.ordinary_status_label ?? "DeepSeek 等 governed executor；Tushare-first 和基础图谱可先走。")}</p>
          <MetricGrid
            items={[
              { label: "下一步", value: String(governedExecutor.ordinary_next_allowed_action ?? "先继续 Tushare-first、Factor light 和 Next Session 本地回放；DeepSeek 单独验收。") },
              { label: "P5 单独补证", value: governedExecutorStandaloneBoundary, tone: "good" },
              { label: "必备治理", value: String(governedExecutor.ordinary_required_before_real_call ?? "需要 model_ledger / sanitizer / redaction review / cost accounting / output acceptance 全部就绪。"), tone: "warn" },
              { label: "非阻塞", value: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "Tushare-first / Factor light / Next Session 可先走" : "待确认", tone: governedExecutor.ordinary_safe_to_ignore_for_basic_maps === true ? "good" : "warn" },
              { label: "阻断状态", value: String(governedExecutor.ordinary_blocking_state ?? "pending_model_ledger_not_blocking_tushare_or_basic_maps"), tone: "warn" },
              { label: "边界", value: String(governedExecutor.ordinary_nonblocking_boundary ?? "DeepSeek 只解释已有证据，不作为数据源、不生成买卖动作。"), tone: "good" }
            ]}
          />
          <details className="developer-audit-details">
            <summary>P5 执行路由详情</summary>
            <p>真实调用入口：{String(governedExecutor.execution_route ?? "POST /api/factor-quant/deepseek-explain")}；scope ticket：{String(governedExecutor.scope_ticket_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket")}。</p>
          </details>
          <p>必须先有 model_ledger、sanitizer、redaction review、cost accounting 和 output acceptance；本页 GET cache 与 React render 都不调用模型。</p>
          <p>DeepSeek 只解释已有证据，不覆盖价格、持仓、因子、operation zones 或 strategy action。</p>
          <StateClarityRail
            label="deepseek governed executor readiness status"
            state={governedExecutorRailState}
            steps={governedExecutorRailSteps}
          />
          <p className="risk-note">P5 准入状态：scope ticket / sanitizer-redaction / model ledger / 普通路径非阻塞；这条状态轨只读本地 cache，不调用 DeepSeek、不阻塞 Tushare-first 或基础图谱。</p>
          <div aria-label="deepseek governed executor nonblocking ordinary paths">
            <h3>不阻塞基础投研路径</h3>
            <p className="risk-note">DeepSeek governed executor 未完成前，普通用户仍可先看 Tushare-first、Factor light 和 Next Session 本地回放。</p>
            <DataLineageTable rows={governedExecutorNonblockingRows} />
          </div>
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
