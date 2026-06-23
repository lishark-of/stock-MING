import { useEffect, useState } from "react";
import { getModelStrategyCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
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
          <p>真实调用入口：{String(governedExecutor.execution_route ?? "POST /api/factor-quant/deepseek-explain")}；scope ticket：{String(governedExecutor.scope_ticket_route ?? "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket")}。</p>
          <p>必须先有 model_ledger、sanitizer、redaction review、cost accounting 和 output acceptance；本页 GET cache 与 React render 都不调用模型。</p>
          <p>DeepSeek 只解释已有证据，不覆盖价格、持仓、因子、operation zones 或 strategy action。</p>
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
    </>
  );
}
