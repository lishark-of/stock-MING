import type { TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import DeepSeekModelStrategyLedger from "./DeepSeekModelStrategyLedger";

export default function TaskLaunchReceipt({ receipt }: { receipt: TaskCreationEnvelope | null }) {
  if (!receipt) return null;
  const task = receipt.data?.task;
  const topLevelCallLedger = receipt.call_ledger ?? [];
  const taskCallLedger = task?.call_ledger ?? [];
  const callLedger = topLevelCallLedger.length ? topLevelCallLedger : taskCallLedger;
  const modelStrategyCallLedger = [...topLevelCallLedger, ...taskCallLedger];
  const warnings = receipt.warnings.length ? receipt.warnings : task?.warnings ?? [];

  return (
    <div className="task-panel">
      <div className="task-panel__head">
        <span>任务创建回执</span>
        <span>{receipt.ok ? "accepted" : String(receipt.error ?? "failed")}</span>
      </div>
      <p>task_id: {String(receipt.data?.task_id ?? "--")}</p>
      <p>task_type: {String(task?.task_type ?? "--")}</p>
      <p>output_packet_key: {String(task?.output_packet_key ?? "--")}</p>
      <p>external_calls_triggered: {String(task?.external_calls_triggered ?? false)}</p>
      <p>Tushare / DeepSeek / GitHub: {String(task?.tushare_called ?? false)} / {String(task?.deepseek_called ?? false)} / {String(task?.github_called ?? false)}</p>
      <p>does_not_execute_trades: {String(task?.does_not_execute_trades ?? true)}</p>
      <p>does_not_modify_strategy_action: {String(task?.does_not_modify_strategy_action ?? true)}</p>
      <p>top_level_call_ledger: {topLevelCallLedger.length}</p>
      <p>task_call_ledger: {taskCallLedger.length}</p>
      <p>按钮任务回执只展示 FastAPI 返回的审计血缘；不调用 Tushare、DeepSeek 或 GitHub。</p>
      {task?.error_message_safe ? <p className="risk-note">error_message_safe: {task.error_message_safe}</p> : null}
      {warnings.length ? <p className="risk-note">{String(warnings[0])}</p> : null}
      <DeepSeekModelStrategyLedger callLedger={modelStrategyCallLedger} />
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无任务创建 call_ledger。</p>}
    </div>
  );
}
