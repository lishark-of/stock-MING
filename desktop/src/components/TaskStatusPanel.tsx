import { useEffect, useRef, useState } from "react";
import { getTask, type TaskRecord } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import JsonDetails from "./JsonDetails";
import StatusBadge from "./StatusBadge";

type Props = {
  taskId: string;
  onSuccess?: () => void;
};

function toneForStatus(status: TaskRecord["status"]) {
  if (status === "success") return "good";
  if (status === "failed" || status === "cancelled") return "bad";
  return "warn";
}

export default function TaskStatusPanel({ taskId, onSuccess }: Props) {
  const [task, setTask] = useState<TaskRecord | null>(null);
  const successNotified = useRef("");

  useEffect(() => {
    if (!taskId) return undefined;
    let active = true;
    const load = () => {
      void getTask(taskId).then((res) => {
        if (active && res.ok) setTask(res.data);
      });
    };
    load();
    const timer = window.setInterval(() => {
      if (!task || task.status === "pending" || task.status === "running") load();
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [taskId, task?.status]);

  useEffect(() => {
    if (task?.status === "success" && task.task_id !== successNotified.current) {
      successNotified.current = task.task_id;
      onSuccess?.();
    }
  }, [onSuccess, task?.status, task?.task_id]);

  if (!taskId) return null;
  if (!task) return <p>任务状态读取中：{taskId}</p>;
  const callLedger = task.call_ledger ?? [];
  const statusHistory = task.status_history ?? [];

  return (
    <div className="task-panel">
      <div className="task-panel__head">
        <StatusBadge label={task.status} tone={toneForStatus(task.status)} />
        <span>{task.task_type}</span>
      </div>
      <progress value={task.progress ?? 0} max={1} />
      <p>{task.current_step}</p>
      <p>task_id: {task.task_id}</p>
      <p>backend: {task.backend ?? "local_fallback"}</p>
      <p>output_packet_key: {task.output_packet_key || "--"}</p>
      <p>external_calls_triggered: {String(task.external_calls_triggered ?? false)}</p>
      <p>Tushare / DeepSeek / GitHub: {String(task.tushare_called ?? false)} / {String(task.deepseek_called ?? false)} / {String(task.github_called ?? false)}</p>
      <p>does_not_execute_trades: {String(task.does_not_execute_trades ?? true)}</p>
      <p>does_not_modify_strategy_action: {String(task.does_not_modify_strategy_action ?? true)}</p>
      <p>call_ledger: {callLedger.length}</p>
      {task.error_message_safe ? <p className="risk-note">{task.error_message_safe}</p> : null}
      {task.warnings?.length ? <p className="risk-note">{task.warnings[0]}</p> : null}
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无 call_ledger 记录。</p>}
      {statusHistory.length ? <JsonDetails title="status_history" data={statusHistory} /> : null}
    </div>
  );
}
