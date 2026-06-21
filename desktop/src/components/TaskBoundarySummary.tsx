import type { TaskRecord } from "../api/client";

export default function TaskBoundarySummary({ task }: { task?: Partial<TaskRecord> | null }) {
  const externalState = task?.external_calls_triggered ? "已触发" : "未触发";
  const tushareState = task?.tushare_called ? "已调用" : "未调用";
  const deepseekState = task?.deepseek_called ? "已调用" : "未调用";
  const githubState = task?.github_called ? "已调用" : "未调用";
  const tradeState = task?.does_not_execute_trades === false ? "存在异常" : "不会执行";
  const strategyState = task?.does_not_modify_strategy_action === false ? "存在异常" : "不会修改";

  return (
    <div className="task-boundary-summary">
      <p>任务类型：{String(task?.task_type ?? "--")}</p>
      <p>输出记录：{String(task?.output_packet_key ?? "--")}</p>
      <p>外联状态：{externalState}</p>
      <p>Tushare / DeepSeek / GitHub：{tushareState} / {deepseekState} / {githubState}</p>
      <p>真实交易：{tradeState}</p>
      <p>交易策略：{strategyState}</p>
      {task?.error_message_safe ? <p className="risk-note">错误说明：{task.error_message_safe}</p> : null}
    </div>
  );
}
