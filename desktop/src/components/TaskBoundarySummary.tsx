import type { TaskRecord } from "../api/client";

export default function TaskBoundarySummary({ task }: { task?: Partial<TaskRecord> | null }) {
  return (
    <div className="task-boundary-summary">
      <p>task_type: {String(task?.task_type ?? "--")}</p>
      <p>output_packet_key: {String(task?.output_packet_key ?? "--")}</p>
      <p>external_calls_triggered: {String(task?.external_calls_triggered ?? false)}</p>
      <p>Tushare / DeepSeek / GitHub: {String(task?.tushare_called ?? false)} / {String(task?.deepseek_called ?? false)} / {String(task?.github_called ?? false)}</p>
      <p>does_not_execute_trades: {String(task?.does_not_execute_trades ?? true)}</p>
      <p>does_not_modify_strategy_action: {String(task?.does_not_modify_strategy_action ?? true)}</p>
      {task?.error_message_safe ? <p className="risk-note">error_message_safe: {task.error_message_safe}</p> : null}
    </div>
  );
}
