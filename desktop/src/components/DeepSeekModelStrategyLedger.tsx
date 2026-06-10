import DataLineageTable from "./DataLineageTable";

type StrategyRow = {
  api: string;
  purpose: unknown;
  model: unknown;
  model_source: unknown;
  config_keys: unknown;
  active_config_key: unknown;
  does_not_hardcode_model: unknown;
  contains_secret: unknown;
  call_policy: unknown;
  external_call_on_cache_read: unknown;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export function extractDeepSeekModelStrategyRows(callLedger: Array<Record<string, unknown>>): StrategyRow[] {
  return callLedger.flatMap((entry) => {
    const requestParams = asRecord(entry.request_params_safe);
    const strategy = asRecord(requestParams.deepseek_model_strategy);
    if (!Object.keys(strategy).length) return [];

    return [
      {
        api: String(entry.api ?? "task_call_ledger"),
        purpose: strategy.purpose ?? "--",
        model: strategy.model ?? "--",
        model_source: strategy.model_source ?? "--",
        config_keys: strategy.config_keys ?? [],
        active_config_key: strategy.active_config_key ?? "--",
        does_not_hardcode_model: strategy.does_not_hardcode_model ?? true,
        contains_secret: strategy.contains_secret ?? false,
        call_policy: strategy.call_policy ?? "manual_only",
        external_call_on_cache_read: strategy.external_call_on_cache_read ?? false
      }
    ];
  });
}

export default function DeepSeekModelStrategyLedger({ callLedger }: { callLedger: Array<Record<string, unknown>> }) {
  const rows = extractDeepSeekModelStrategyRows(callLedger);
  if (!rows.length) return null;

  return (
    <div className="task-model-strategy">
      <p>DeepSeek 模型策略血缘：来自 request_params_safe.deepseek_model_strategy；只读展示，不调用模型。</p>
      <DataLineageTable rows={rows} />
    </div>
  );
}
