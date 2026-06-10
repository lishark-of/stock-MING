type ChartContract = {
  source_packet?: unknown;
  external_calls_triggered?: unknown;
  tushare_called?: unknown;
  deepseek_called?: unknown;
  github_called?: unknown;
  does_not_execute_trades?: unknown;
  frontend_computes_trade_action?: unknown;
  does_not_modify_action?: unknown;
  does_not_modify_operation_zones?: unknown;
};

type SafetyItem = {
  label: string;
  value: string;
};

function isTrue(value: unknown): boolean {
  return value === true;
}

function isFalse(value: unknown): boolean {
  return value === false;
}

export default function ChartSafetyStrip({
  contract,
  source,
  extraItems = []
}: {
  contract?: ChartContract | null;
  source?: unknown;
  extraItems?: SafetyItem[];
}) {
  const resolvedSource = contract?.source_packet ?? source ?? "cache_payload";
  return (
    <div className="chart-safety-strip">
      <span>来源：{String(resolvedSource)}</span>
      {extraItems.map((item) => (
        <span key={`${item.label}:${item.value}`}>
          {item.label}：{item.value}
        </span>
      ))}
      <span>外部调用：{isTrue(contract?.external_calls_triggered) ? "存在" : "无"}</span>
      <span>Tushare：{isTrue(contract?.tushare_called) ? "已调用" : "未调用"}</span>
      <span>DeepSeek：{isTrue(contract?.deepseek_called) ? "已调用" : "未调用"}</span>
      <span>GitHub：{isTrue(contract?.github_called) ? "已调用" : "未调用"}</span>
      <span>真实交易：{isFalse(contract?.does_not_execute_trades) ? "可能" : "禁止"}</span>
      <span>前端算交易动作：{isTrue(contract?.frontend_computes_trade_action) ? "是" : "否"}</span>
      <span>改 action：{isFalse(contract?.does_not_modify_action) ? "可能" : "不会"}</span>
      <span>改操作区：{isFalse(contract?.does_not_modify_operation_zones) ? "可能" : "不会"}</span>
    </div>
  );
}
